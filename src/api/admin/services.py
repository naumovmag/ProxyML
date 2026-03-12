import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_current_admin
from src.services.service_registry import (
    list_services, get_service_by_id, create_service, update_service, delete_service
)
from src.schemas.service import ServiceCreate, ServiceUpdate, ServiceRead

router = APIRouter(dependencies=[Depends(get_current_admin)])

@router.get("/services", response_model=list[ServiceRead])
async def admin_list_services(session: AsyncSession = Depends(get_async_session)):
    return await list_services(session)

@router.get("/services/{service_id}", response_model=ServiceRead)
async def admin_get_service(service_id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    svc = await get_service_by_id(session, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return svc

@router.post("/services", response_model=ServiceRead, status_code=201)
async def admin_create_service(data: ServiceCreate, session: AsyncSession = Depends(get_async_session)):
    return await create_service(session, data)

@router.put("/services/{service_id}", response_model=ServiceRead)
async def admin_update_service(service_id: uuid.UUID, data: ServiceUpdate, session: AsyncSession = Depends(get_async_session)):
    svc = await update_service(session, service_id, data)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return svc

@router.delete("/services/{service_id}", status_code=204)
async def admin_delete_service(service_id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    deleted = await delete_service(session, service_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Service not found")
