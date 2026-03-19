import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_current_admin
from src.services.service_access import check_service_access, list_accessible_services
from src.services.health_checker import check_service_health
from src.schemas.health import ServiceHealthCheck, HealthReportResponse, HealthReportItem
from src.models.admin_user import AdminUser

router = APIRouter()


@router.post("/services/{service_id}/check", response_model=ServiceHealthCheck)
async def check_connection(
    service_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    service, role = await check_service_access(session, service_id, admin.id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    result = await check_service_health(service)
    return ServiceHealthCheck(
        service_id=str(service.id),
        service_name=service.name,
        **result,
    )


@router.post("/services-check-all", response_model=HealthReportResponse)
async def check_all_services(
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    items_data = await list_accessible_services(session, admin.id)
    services = [item["service"] for item in items_data]

    async def check_one(svc):
        result = await check_service_health(svc)
        return HealthReportItem(
            service_id=str(svc.id),
            service_name=svc.name,
            slug=svc.slug,
            is_active=svc.is_active,
            **result,
        )

    items = await asyncio.gather(*[check_one(s) for s in services])
    items = list(items)
    total = len(items)
    healthy = sum(1 for i in items if i.status == "ok")
    warning = sum(1 for i in items if i.status == "warning")
    unhealthy = sum(1 for i in items if i.status == "error")
    unconfigured = sum(1 for i in items if i.status == "unknown")

    return HealthReportResponse(
        items=items,
        total=total,
        healthy=healthy,
        warning=warning,
        unhealthy=unhealthy,
        unconfigured=unconfigured,
    )
