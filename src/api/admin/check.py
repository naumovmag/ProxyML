import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_current_admin
from src.services.service_registry import get_service_by_id
from src.services.health_checker import check_service_health
from src.schemas.health import ServiceHealthCheck

router = APIRouter(dependencies=[Depends(get_current_admin)])

@router.post("/services/{service_id}/check", response_model=ServiceHealthCheck)
async def check_connection(service_id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    service = await get_service_by_id(session, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    result = await check_service_health(service)
    return ServiceHealthCheck(
        service_id=str(service.id),
        service_name=service.name,
        **result,
    )
