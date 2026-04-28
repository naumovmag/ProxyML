import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.admin_user import AdminUser
from src.models.service import Service
from src.models.service_share import ServiceShare


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


async def get_shared_service_ids(
    session: AsyncSession, user_id: uuid.UUID
) -> list[uuid.UUID]:
    """Returns list of service IDs shared with the user (no own services)."""
    result = await session.execute(
        select(ServiceShare.service_id).where(ServiceShare.shared_with_user_id == user_id)
    )
    return [row[0] for row in result.all()]


async def check_service_access(
    session: AsyncSession, service_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Service | None, str]:
    """Returns (service, role='owner'|'shared') or (None, '') if no access."""
    row = (
        await session.execute(
            select(Service, ServiceShare.id)
            .join(
                ServiceShare,
                (ServiceShare.service_id == Service.id)
                & (ServiceShare.shared_with_user_id == user_id),
                isouter=True,
            )
            .where(Service.id == service_id)
        )
    ).first()
    if not row:
        return None, ""
    service, share_id = row
    if service.owner_id == user_id:
        return service, "owner"
    if share_id is not None:
        return service, "shared"
    return None, ""


async def list_accessible_services(
    session: AsyncSession, user_id: uuid.UUID, active_only: bool = False
) -> list[dict]:
    """Own + shared services. Returns list of dicts with service data + role/owner info/shared_with_count."""

    # --- Own services + share counts in a single SELECT (correlated subquery) ---
    shared_count_subq = (
        select(func.count(ServiceShare.id))
        .where(ServiceShare.service_id == Service.id)
        .correlate(Service)
        .scalar_subquery()
    )
    own_stmt = (
        select(Service, shared_count_subq.label("shared_count"))
        .where(Service.owner_id == user_id)
        .order_by(Service.name)
    )
    if active_only:
        own_stmt = own_stmt.where(Service.is_active == True)
    own_result = await session.execute(own_stmt)
    own_rows = own_result.all()

    # Get owner user info (one SELECT, same for all own services)
    owner_result = await session.execute(select(AdminUser).where(AdminUser.id == user_id))
    owner_user = owner_result.scalar_one_or_none()

    items: list[dict] = []
    for s, shared_count in own_rows:
        items.append({
            "service": s,
            "role": "owner",
            "owner_username": owner_user.username if owner_user else None,
            "owner_display_name": owner_user.display_name if owner_user else None,
            "shared_with_count": shared_count or 0,
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
