import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_current_superadmin
from src.models.admin_user import AdminUser
from src.schemas.auth import UserRead
from pydantic import BaseModel


class UserUpdateAdmin(BaseModel):
    is_approved: bool | None = None
    is_active: bool | None = None
    is_superadmin: bool | None = None
    display_name: str | None = None
    email: str | None = None


router = APIRouter()


@router.get("/users", response_model=list[UserRead])
async def list_users(
    admin: AdminUser = Depends(get_current_superadmin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(select(AdminUser).order_by(AdminUser.created_at.desc()))
    return [UserRead.model_validate(u) for u in result.scalars().all()]


@router.get("/users/{user_id}", response_model=UserRead)
async def get_user(
    user_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_superadmin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(select(AdminUser).where(AdminUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(user)


@router.put("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdateAdmin,
    admin: AdminUser = Depends(get_current_superadmin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(select(AdminUser).where(AdminUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    update = data.model_dump(exclude_unset=True)
    # Prevent superadmin from removing their own superadmin/active/approved status
    if user_id == admin.id:
        if update.get("is_superadmin") is False:
            raise HTTPException(status_code=400, detail="Cannot remove your own superadmin rights")
        if update.get("is_active") is False:
            raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
        if update.get("is_approved") is False:
            raise HTTPException(status_code=400, detail="Cannot unapprove yourself")
    for key, value in update.items():
        setattr(user, key, value)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.post("/users/{user_id}/approve", response_model=UserRead)
async def approve_user(
    user_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_superadmin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(select(AdminUser).where(AdminUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_approved = True
    user.is_active = True
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.post("/users/{user_id}/reject", response_model=UserRead)
async def reject_user(
    user_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_superadmin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(select(AdminUser).where(AdminUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_approved = False
    user.is_active = False
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_superadmin),
    session: AsyncSession = Depends(get_async_session),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    result = await session.execute(select(AdminUser).where(AdminUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await session.delete(user)
    await session.commit()
