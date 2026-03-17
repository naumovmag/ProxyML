import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_current_admin
from src.models.service_group import ServiceGroup
from src.models.admin_user import AdminUser
from src.schemas.service import ServiceGroupCreate, ServiceGroupUpdate, ServiceGroupRead

router = APIRouter()


@router.get("/service-groups", response_model=list[ServiceGroupRead])
async def list_groups(
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(ServiceGroup)
        .where(ServiceGroup.owner_id == admin.id)
        .order_by(ServiceGroup.sort_order, ServiceGroup.name)
    )
    return list(result.scalars().all())


@router.post("/service-groups", response_model=ServiceGroupRead, status_code=201)
async def create_group(
    data: ServiceGroupCreate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    group = ServiceGroup(**data.model_dump(), owner_id=admin.id)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group


@router.put("/service-groups/{group_id}", response_model=ServiceGroupRead)
async def update_group(
    group_id: uuid.UUID,
    data: ServiceGroupUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(ServiceGroup).where(ServiceGroup.id == group_id, ServiceGroup.owner_id == admin.id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(group, key, value)
    await session.commit()
    await session.refresh(group)
    return group


@router.delete("/service-groups/{group_id}", status_code=204)
async def delete_group(
    group_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        delete(ServiceGroup).where(ServiceGroup.id == group_id, ServiceGroup.owner_id == admin.id)
    )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Group not found")
