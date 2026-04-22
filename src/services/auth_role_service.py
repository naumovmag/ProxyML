import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.auth_permission import AuthPermission
from src.models.auth_role import AuthRole, AuthRolePermission, AuthUserRole
from src.models.auth_user import AuthUser
from src.schemas.auth_role import PermissionCreate, PermissionUpdate, RoleCreate, RoleUpdate

# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

async def list_permissions(session: AsyncSession, auth_system_id: uuid.UUID) -> list[AuthPermission]:
    result = await session.execute(
        select(AuthPermission)
        .where(AuthPermission.auth_system_id == auth_system_id)
        .order_by(AuthPermission.slug)
    )
    return list(result.scalars().all())


async def create_permission(
    session: AsyncSession,
    auth_system_id: uuid.UUID,
    data: PermissionCreate,
) -> AuthPermission:
    existing = await session.execute(
        select(AuthPermission.id).where(
            AuthPermission.auth_system_id == auth_system_id,
            AuthPermission.slug == data.slug,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Permission slug already exists in this auth system")

    perm = AuthPermission(
        auth_system_id=auth_system_id,
        slug=data.slug,
        name=data.name,
        description=data.description,
    )
    session.add(perm)
    await session.commit()
    await session.refresh(perm)
    return perm


async def update_permission(
    session: AsyncSession,
    auth_system_id: uuid.UUID,
    permission_id: uuid.UUID,
    data: PermissionUpdate,
) -> AuthPermission:
    result = await session.execute(
        select(AuthPermission).where(
            AuthPermission.id == permission_id,
            AuthPermission.auth_system_id == auth_system_id,
        )
    )
    perm = result.scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")

    if data.name is not None:
        perm.name = data.name
    if data.description is not None:
        perm.description = data.description

    await session.commit()
    await session.refresh(perm)
    return perm


async def delete_permission(
    session: AsyncSession,
    auth_system_id: uuid.UUID,
    permission_id: uuid.UUID,
) -> None:
    result = await session.execute(
        select(AuthPermission).where(
            AuthPermission.id == permission_id,
            AuthPermission.auth_system_id == auth_system_id,
        )
    )
    perm = result.scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    await session.delete(perm)
    await session.commit()


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

async def list_roles(session: AsyncSession, auth_system_id: uuid.UUID) -> list[AuthRole]:
    result = await session.execute(
        select(AuthRole)
        .where(AuthRole.auth_system_id == auth_system_id)
        .options(selectinload(AuthRole.permissions))
        .order_by(AuthRole.slug)
    )
    return list(result.scalars().all())


async def _validate_permission_ids(
    session: AsyncSession,
    auth_system_id: uuid.UUID,
    permission_ids: list[uuid.UUID],
) -> None:
    if not permission_ids:
        return
    result = await session.execute(
        select(AuthPermission.id).where(
            AuthPermission.id.in_(permission_ids),
            AuthPermission.auth_system_id == auth_system_id,
        )
    )
    found = set(result.scalars().all())
    missing = set(permission_ids) - found
    if missing:
        raise HTTPException(status_code=400, detail=f"Permissions not found in this auth system: {[str(m) for m in missing]}")


async def _unset_existing_default(session: AsyncSession, auth_system_id: uuid.UUID, exclude_role_id: uuid.UUID | None = None) -> None:
    stmt = select(AuthRole).where(
        AuthRole.auth_system_id == auth_system_id,
        AuthRole.is_default == True,
    )
    if exclude_role_id:
        stmt = stmt.where(AuthRole.id != exclude_role_id)
    result = await session.execute(stmt)
    for role in result.scalars().all():
        role.is_default = False


async def _unset_existing_admin_role(session: AsyncSession, auth_system_id: uuid.UUID, exclude_role_id: uuid.UUID | None = None) -> None:
    stmt = select(AuthRole).where(
        AuthRole.auth_system_id == auth_system_id,
        AuthRole.is_admin_role == True,
    )
    if exclude_role_id:
        stmt = stmt.where(AuthRole.id != exclude_role_id)
    result = await session.execute(stmt)
    for role in result.scalars().all():
        role.is_admin_role = False


async def create_role(
    session: AsyncSession,
    auth_system_id: uuid.UUID,
    data: RoleCreate,
) -> AuthRole:
    existing = await session.execute(
        select(AuthRole.id).where(
            AuthRole.auth_system_id == auth_system_id,
            AuthRole.slug == data.slug,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Role slug already exists in this auth system")

    await _validate_permission_ids(session, auth_system_id, data.permission_ids)

    if data.is_default:
        await _unset_existing_default(session, auth_system_id)
    if data.is_admin_role:
        await _unset_existing_admin_role(session, auth_system_id)

    role = AuthRole(
        auth_system_id=auth_system_id,
        slug=data.slug,
        name=data.name,
        description=data.description,
        is_default=data.is_default,
        is_admin_role=data.is_admin_role,
    )
    session.add(role)
    await session.flush()  # get role.id before adding permissions

    for perm_id in data.permission_ids:
        session.add(AuthRolePermission(role_id=role.id, permission_id=perm_id))

    await session.commit()

    # Reload with permissions
    result = await session.execute(
        select(AuthRole)
        .where(AuthRole.id == role.id)
        .options(selectinload(AuthRole.permissions))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def get_role(
    session: AsyncSession,
    auth_system_id: uuid.UUID,
    role_id: uuid.UUID,
) -> AuthRole:
    result = await session.execute(
        select(AuthRole)
        .where(AuthRole.id == role_id, AuthRole.auth_system_id == auth_system_id)
        .options(selectinload(AuthRole.permissions))
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


async def update_role(
    session: AsyncSession,
    auth_system_id: uuid.UUID,
    role_id: uuid.UUID,
    data: RoleUpdate,
) -> AuthRole:
    result = await session.execute(
        select(AuthRole)
        .where(AuthRole.id == role_id, AuthRole.auth_system_id == auth_system_id)
        .options(selectinload(AuthRole.permissions))
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if data.name is not None:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.is_default is not None:
        if data.is_default:
            await _unset_existing_default(session, auth_system_id, exclude_role_id=role_id)
        role.is_default = data.is_default
    if data.is_admin_role is not None:
        if data.is_admin_role:
            await _unset_existing_admin_role(session, auth_system_id, exclude_role_id=role_id)
        role.is_admin_role = data.is_admin_role

    await session.commit()
    await session.refresh(role)
    # reload permissions after refresh
    result2 = await session.execute(
        select(AuthRole)
        .where(AuthRole.id == role_id)
        .options(selectinload(AuthRole.permissions))
        .execution_options(populate_existing=True)
    )
    return result2.scalar_one()


async def delete_role(
    session: AsyncSession,
    auth_system_id: uuid.UUID,
    role_id: uuid.UUID,
) -> None:
    result = await session.execute(
        select(AuthRole).where(AuthRole.id == role_id, AuthRole.auth_system_id == auth_system_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete a system role")
    await session.delete(role)
    await session.commit()


async def set_role_permissions(
    session: AsyncSession,
    auth_system_id: uuid.UUID,
    role_id: uuid.UUID,
    permission_ids: list[uuid.UUID],
) -> AuthRole:
    result = await session.execute(
        select(AuthRole).where(AuthRole.id == role_id, AuthRole.auth_system_id == auth_system_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    await _validate_permission_ids(session, auth_system_id, permission_ids)

    # Full replacement: delete existing, insert new
    await session.execute(
        delete(AuthRolePermission).where(AuthRolePermission.role_id == role_id)
    )
    for perm_id in permission_ids:
        session.add(AuthRolePermission(role_id=role_id, permission_id=perm_id))

    await session.commit()

    result2 = await session.execute(
        select(AuthRole)
        .where(AuthRole.id == role_id)
        .options(selectinload(AuthRole.permissions))
        .execution_options(populate_existing=True)
    )
    return result2.scalar_one()


# ---------------------------------------------------------------------------
# User roles
# ---------------------------------------------------------------------------

async def get_user_roles(session: AsyncSession, user_id: uuid.UUID) -> list[AuthRole]:
    result = await session.execute(
        select(AuthRole)
        .join(AuthUserRole, AuthUserRole.role_id == AuthRole.id)
        .where(AuthUserRole.auth_user_id == user_id)
        .options(selectinload(AuthRole.permissions))
        .order_by(AuthRole.slug)
    )
    return list(result.scalars().all())


async def set_user_roles(
    session: AsyncSession,
    auth_system_id: uuid.UUID,
    user_id: uuid.UUID,
    role_ids: list[uuid.UUID],
) -> list[AuthRole]:
    # Verify user belongs to auth_system
    user_result = await session.execute(
        select(AuthUser.id).where(AuthUser.id == user_id, AuthUser.auth_system_id == auth_system_id)
    )
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found in this auth system")

    # Verify all roles belong to this auth_system
    if role_ids:
        roles_result = await session.execute(
            select(AuthRole.id).where(
                AuthRole.id.in_(role_ids),
                AuthRole.auth_system_id == auth_system_id,
            )
        )
        found_ids = set(roles_result.scalars().all())
        missing = set(role_ids) - found_ids
        if missing:
            raise HTTPException(status_code=400, detail=f"Roles not found in this auth system: {[str(m) for m in missing]}")

    # Full replacement
    await session.execute(
        delete(AuthUserRole).where(AuthUserRole.auth_user_id == user_id)
    )
    for role_id in role_ids:
        session.add(AuthUserRole(auth_user_id=user_id, role_id=role_id))

    await session.commit()
    return await get_user_roles(session, user_id)


async def add_user_role(
    session: AsyncSession,
    auth_system_id: uuid.UUID,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    assigned_by: uuid.UUID | None,
) -> None:
    # Verify role belongs to auth_system
    role_result = await session.execute(
        select(AuthRole.id).where(AuthRole.id == role_id, AuthRole.auth_system_id == auth_system_id)
    )
    if not role_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Role not found in this auth system")

    # Idempotent: check if already assigned
    existing = await session.execute(
        select(AuthUserRole).where(
            AuthUserRole.auth_user_id == user_id,
            AuthUserRole.role_id == role_id,
        )
    )
    if existing.scalar_one_or_none():
        return

    session.add(AuthUserRole(auth_user_id=user_id, role_id=role_id, assigned_by=assigned_by))
    await session.commit()


async def remove_user_role(
    session: AsyncSession,
    auth_system_id: uuid.UUID,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
) -> None:
    # Verify role belongs to auth_system
    role_result = await session.execute(
        select(AuthRole.id).where(AuthRole.id == role_id, AuthRole.auth_system_id == auth_system_id)
    )
    if not role_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Role not found in this auth system")

    result = await session.execute(
        select(AuthUserRole).where(
            AuthUserRole.auth_user_id == user_id,
            AuthUserRole.role_id == role_id,
        )
    )
    ur = result.scalar_one_or_none()
    if ur:
        await session.delete(ur)
        await session.commit()


async def get_user_permissions(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    roles = await get_user_roles(session, user_id)
    slugs: set[str] = set()
    for role in roles:
        for perm in role.permissions:
            slugs.add(perm.slug)
    return sorted(slugs)


async def get_default_role(session: AsyncSession, auth_system_id: uuid.UUID) -> AuthRole | None:
    result = await session.execute(
        select(AuthRole).where(
            AuthRole.auth_system_id == auth_system_id,
            AuthRole.is_default == True,
        )
    )
    return result.scalar_one_or_none()


async def user_has_admin_role(session: AsyncSession, user_id: uuid.UUID) -> bool:
    """True if the user has at least one role with is_admin_role=True."""
    result = await session.execute(
        select(AuthRole.id)
        .join(AuthUserRole, AuthUserRole.role_id == AuthRole.id)
        .where(AuthUserRole.auth_user_id == user_id, AuthRole.is_admin_role == True)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def list_users_in_system(
    session: AsyncSession,
    auth_system_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[AuthUser]:
    result = await session.execute(
        select(AuthUser)
        .where(AuthUser.auth_system_id == auth_system_id)
        .options(selectinload(AuthUser.roles))
        .order_by(AuthUser.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
