import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_admin
from src.db.session import get_async_session
from src.models.admin_user import AdminUser
from src.models.auth_system import AuthSystem
from src.models.auth_user import AuthUser
from src.schemas.auth_role import (
    PermissionCreate,
    PermissionRead,
    PermissionUpdate,
    RoleCreate,
    RolePermissionsSet,
    RoleRead,
    RoleUpdate,
    UserRoleAdd,
    UserRolesAssign,
)
from src.services import auth_role_service

router = APIRouter()


async def _get_system_or_404(
    system_id: uuid.UUID,
    admin: AdminUser,
    session: AsyncSession,
) -> None:
    result = await session.execute(
        select(AuthSystem.id).where(
            AuthSystem.id == system_id,
            AuthSystem.owner_id == admin.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Auth system not found")


async def _assert_user_in_system(
    session: AsyncSession,
    system_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    result = await session.execute(
        select(AuthUser.id).where(
            AuthUser.id == user_id,
            AuthUser.auth_system_id == system_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found in this auth system")


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

@router.get("/auth-systems/{system_id}/permissions", response_model=list[PermissionRead])
async def list_permissions(
    system_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system_or_404(system_id, admin, session)
    return await auth_role_service.list_permissions(session, system_id)


@router.post("/auth-systems/{system_id}/permissions", response_model=PermissionRead, status_code=201)
async def create_permission(
    system_id: uuid.UUID,
    data: PermissionCreate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system_or_404(system_id, admin, session)
    return await auth_role_service.create_permission(session, system_id, data)


@router.put("/auth-systems/{system_id}/permissions/{permission_id}", response_model=PermissionRead)
async def update_permission(
    system_id: uuid.UUID,
    permission_id: uuid.UUID,
    data: PermissionUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system_or_404(system_id, admin, session)
    return await auth_role_service.update_permission(session, system_id, permission_id, data)


@router.delete("/auth-systems/{system_id}/permissions/{permission_id}", status_code=204)
async def delete_permission(
    system_id: uuid.UUID,
    permission_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system_or_404(system_id, admin, session)
    await auth_role_service.delete_permission(session, system_id, permission_id)


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

@router.get("/auth-systems/{system_id}/roles", response_model=list[RoleRead])
async def list_roles(
    system_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system_or_404(system_id, admin, session)
    return await auth_role_service.list_roles(session, system_id)


@router.post("/auth-systems/{system_id}/roles", response_model=RoleRead, status_code=201)
async def create_role(
    system_id: uuid.UUID,
    data: RoleCreate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system_or_404(system_id, admin, session)
    return await auth_role_service.create_role(session, system_id, data)


@router.get("/auth-systems/{system_id}/roles/{role_id}", response_model=RoleRead)
async def get_role(
    system_id: uuid.UUID,
    role_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system_or_404(system_id, admin, session)
    return await auth_role_service.get_role(session, system_id, role_id)


@router.put("/auth-systems/{system_id}/roles/{role_id}", response_model=RoleRead)
async def update_role(
    system_id: uuid.UUID,
    role_id: uuid.UUID,
    data: RoleUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system_or_404(system_id, admin, session)
    return await auth_role_service.update_role(session, system_id, role_id, data)


@router.delete("/auth-systems/{system_id}/roles/{role_id}", status_code=204)
async def delete_role(
    system_id: uuid.UUID,
    role_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system_or_404(system_id, admin, session)
    await auth_role_service.delete_role(session, system_id, role_id)


@router.put("/auth-systems/{system_id}/roles/{role_id}/permissions", response_model=RoleRead)
async def set_role_permissions(
    system_id: uuid.UUID,
    role_id: uuid.UUID,
    data: RolePermissionsSet,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system_or_404(system_id, admin, session)
    return await auth_role_service.set_role_permissions(session, system_id, role_id, data.permission_ids)


# ---------------------------------------------------------------------------
# User roles
# ---------------------------------------------------------------------------

@router.get("/auth-systems/{system_id}/users/{user_id}/roles", response_model=list[RoleRead])
async def get_user_roles(
    system_id: uuid.UUID,
    user_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system_or_404(system_id, admin, session)
    await _assert_user_in_system(session, system_id, user_id)
    return await auth_role_service.get_user_roles(session, user_id)


@router.put("/auth-systems/{system_id}/users/{user_id}/roles", response_model=list[RoleRead])
async def set_user_roles(
    system_id: uuid.UUID,
    user_id: uuid.UUID,
    data: UserRolesAssign,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system_or_404(system_id, admin, session)
    return await auth_role_service.set_user_roles(session, system_id, user_id, data.role_ids)


@router.post("/auth-systems/{system_id}/users/{user_id}/roles", status_code=204)
async def add_user_role(
    system_id: uuid.UUID,
    user_id: uuid.UUID,
    data: UserRoleAdd,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system_or_404(system_id, admin, session)
    await _assert_user_in_system(session, system_id, user_id)
    await auth_role_service.add_user_role(session, system_id, user_id, data.role_id, admin.id)


@router.delete("/auth-systems/{system_id}/users/{user_id}/roles/{role_id}", status_code=204)
async def remove_user_role(
    system_id: uuid.UUID,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system_or_404(system_id, admin, session)
    await _assert_user_in_system(session, system_id, user_id)
    await auth_role_service.remove_user_role(session, system_id, user_id, role_id)
