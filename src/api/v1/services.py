from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.services.service_registry import list_services, get_service_by_slug
from src.schemas.service import ServiceCatalogItem

router = APIRouter()

@router.get("/services", response_model=list[ServiceCatalogItem])
async def catalog(session: AsyncSession = Depends(get_async_session)):
    services = await list_services(session, active_only=True)
    return services

@router.get("/services/{slug}")
async def service_detail(slug: str, session: AsyncSession = Depends(get_async_session)):
    service = await get_service_by_slug(session, slug)
    if not service or not service.is_active:
        raise HTTPException(status_code=404, detail="Service not found")
    return ServiceCatalogItem.model_validate(service)
