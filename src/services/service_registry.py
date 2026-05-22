import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache.service_cache import (
    cache_get_by_id,
    cache_get_by_slug,
    cache_invalidate,
    cache_set,
)
from src.models.service import Service
from src.schemas.service import ServiceCreate, ServiceUpdate


class FallbackValidationError(Exception):
    pass


async def _validate_fallback(
    session: AsyncSession,
    service_id: uuid.UUID | None,
    service_type: str,
    fallback_id: uuid.UUID | None,
) -> None:
    if not fallback_id:
        return
    if service_id and fallback_id == service_id:
        raise FallbackValidationError("Service cannot be its own fallback")
    # Validation must not read from Redis cache — stale data could let through
    # cycles or service_type mismatches that the user has just fixed.
    fallback = await _db_get_service_by_id(session, fallback_id)
    if not fallback:
        raise FallbackValidationError("Fallback service not found")
    if fallback.service_type != service_type:
        raise FallbackValidationError(
            f"Fallback service type mismatch: expected '{service_type}', got '{fallback.service_type}'"
        )
    visited: set[uuid.UUID] = set()
    if service_id:
        visited.add(service_id)
    current = fallback
    while current:
        if current.id in visited:
            raise FallbackValidationError("Fallback chain contains a cycle")
        visited.add(current.id)
        if not current.fallback_service_id:
            break
        current = await _db_get_service_by_id(session, current.fallback_service_id)


async def _db_get_service_by_id(session: AsyncSession, service_id: uuid.UUID) -> Service | None:
    result = await session.execute(select(Service).where(Service.id == service_id))
    return result.scalar_one_or_none()


async def list_services(
    session: AsyncSession,
    active_only: bool = False,
    owner_id: uuid.UUID | None = None,
) -> list[Service]:
    stmt = select(Service).order_by(Service.name)
    if active_only:
        stmt = stmt.where(Service.is_active == True)
    if owner_id:
        stmt = stmt.where(Service.owner_id == owner_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_service_by_id(session: AsyncSession, service_id: uuid.UUID) -> Service | None:
    cached = await cache_get_by_id(service_id)
    if cached is not None:
        return cached
    result = await session.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    if service is not None:
        session.expunge(service)
        await cache_set(service)
    return service


async def get_service_by_slug(session: AsyncSession, slug: str) -> Service | None:
    cached = await cache_get_by_slug(slug)
    if cached is not None:
        return cached
    result = await session.execute(select(Service).where(Service.slug == slug))
    service = result.scalar_one_or_none()
    if service is not None:
        session.expunge(service)
        await cache_set(service)
    return service


async def create_service(session: AsyncSession, data: ServiceCreate, owner_id: uuid.UUID | None = None) -> Service:
    dump = data.model_dump()
    if dump.get("fallback_service_id"):
        await _validate_fallback(session, None, dump["service_type"], dump["fallback_service_id"])
    dump["owner_id"] = owner_id
    service = Service(**dump)
    session.add(service)
    await session.commit()
    await session.refresh(service)
    await cache_invalidate(service.slug, service.id)
    return service


async def update_service(session: AsyncSession, service_id: uuid.UUID, data: ServiceUpdate) -> Service | None:
    result = await session.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        return None
    old_slug = service.slug
    update_data = data.model_dump(exclude_unset=True)
    if update_data.pop("clear_fallback", False):
        service.fallback_service_id = None
        service.fallback_on_statuses = None
        update_data.pop("fallback_service_id", None)
        update_data.pop("fallback_on_statuses", None)
    else:
        fallback_id = update_data.get("fallback_service_id")
        if fallback_id:
            svc_type = update_data.get("service_type", service.service_type)
            await _validate_fallback(session, service_id, svc_type, fallback_id)
    for key, value in update_data.items():
        setattr(service, key, value)
    await session.commit()
    await session.refresh(service)
    await cache_invalidate(old_slug, service.id)
    if service.slug != old_slug:
        await cache_invalidate(service.slug, None)
    return service


async def delete_service(session: AsyncSession, service_id: uuid.UUID) -> bool:
    result = await session.execute(
        delete(Service).where(Service.id == service_id).returning(Service.slug)
    )
    slug = result.scalar_one_or_none()
    await session.commit()
    if slug is not None:
        await cache_invalidate(slug, service_id)
        return True
    return False
