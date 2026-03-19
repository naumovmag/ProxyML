import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.service import Service
from src.models.service_share import ServiceShare
from src.models.admin_user import AdminUser


async def get_accessible_service_ids(
    session: AsyncSession, user_id: uuid.UUID
) -> list[uuid.UUID]:
    """Returns list of service IDs the user owns or has shares for."""
    own_result = await session.execute(
        select(Service.id).where(Service.owner_id == user_id)
    )
    ids = [row[0] for row in own_result.all()]

    shared_result = await session.execute(
        select(ServiceShare.service_id).where(ServiceShare.shared_with_user_id == user_id)
    )
    ids.extend(row[0] for row in shared_result.all())
    return ids


async def check_service_access(
    session: AsyncSession, service_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Service | None, str]:
    """Returns (service, role='owner'|'shared') or (None, '') if no access."""
    result = await session.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        return None, ""
    if service.owner_id == user_id:
        return service, "owner"
    share_result = await session.execute(
        select(ServiceShare.id).where(
            ServiceShare.service_id == service_id,
            ServiceShare.shared_with_user_id == user_id,
        )
    )
    if share_result.scalar_one_or_none() is not None:
        return service, "shared"
    return None, ""


async def list_accessible_services(
    session: AsyncSession, user_id: uuid.UUID, active_only: bool = False
) -> list[dict]:
    """Own + shared services. Returns list of dicts with service data + role/owner info/shared_with_count."""

    # --- Own services ---
    own_stmt = select(Service).where(Service.owner_id == user_id).order_by(Service.name)
    if active_only:
        own_stmt = own_stmt.where(Service.is_active == True)
    own_result = await session.execute(own_stmt)
    own_services = list(own_result.scalars().all())

    # Get owner user info
    owner_result = await session.execute(select(AdminUser).where(AdminUser.id == user_id))
    owner_user = owner_result.scalar_one_or_none()

    # Count shares for own services
    own_ids = [s.id for s in own_services]
    share_counts: dict[uuid.UUID, int] = {}
    if own_ids:
        count_stmt = (
            select(ServiceShare.service_id, func.count(ServiceShare.id))
            .where(ServiceShare.service_id.in_(own_ids))
            .group_by(ServiceShare.service_id)
        )
        count_result = await session.execute(count_stmt)
        for sid, cnt in count_result.all():
            share_counts[sid] = cnt

    items: list[dict] = []
    for s in own_services:
        items.append({
            "service": s,
            "role": "owner",
            "owner_username": owner_user.username if owner_user else None,
            "owner_display_name": owner_user.display_name if owner_user else None,
            "shared_with_count": share_counts.get(s.id, 0),
        })

    # --- Shared services ---
    shared_stmt = (
        select(Service, ServiceShare, AdminUser)
        .join(ServiceShare, ServiceShare.service_id == Service.id)
        .join(AdminUser, AdminUser.id == Service.owner_id)
        .where(ServiceShare.shared_with_user_id == user_id)
        .order_by(Service.name)
    )
    if active_only:
        shared_stmt = shared_stmt.where(Service.is_active == True)
    shared_result = await session.execute(shared_stmt)

    for service, share, owner in shared_result.all():
        items.append({
            "service": service,
            "role": "shared",
            "owner_username": owner.username,
            "owner_display_name": owner.display_name,
            "shared_with_count": 0,
            "override_group_id": share.group_id,
        })

    return items
