import uuid
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.service import Service
from src.schemas.service import ServiceCreate, ServiceUpdate

async def list_services(session: AsyncSession, active_only: bool = False) -> list[Service]:
    stmt = select(Service).order_by(Service.name)
    if active_only:
        stmt = stmt.where(Service.is_active == True)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_service_by_id(session: AsyncSession, service_id: uuid.UUID) -> Service | None:
    result = await session.execute(select(Service).where(Service.id == service_id))
    return result.scalar_one_or_none()

async def get_service_by_slug(session: AsyncSession, slug: str) -> Service | None:
    result = await session.execute(select(Service).where(Service.slug == slug))
    return result.scalar_one_or_none()

async def create_service(session: AsyncSession, data: ServiceCreate) -> Service:
    service = Service(**data.model_dump())
    session.add(service)
    await session.commit()
    await session.refresh(service)
    return service

async def update_service(session: AsyncSession, service_id: uuid.UUID, data: ServiceUpdate) -> Service | None:
    service = await get_service_by_id(session, service_id)
    if not service:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(service, key, value)
    await session.commit()
    await session.refresh(service)
    return service

async def delete_service(session: AsyncSession, service_id: uuid.UUID) -> bool:
    result = await session.execute(delete(Service).where(Service.id == service_id))
    await session.commit()
    return result.rowcount > 0
