import uuid
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_current_admin
from src.models.admin_user import AdminUser
from src.models.auth_system import AuthSystem
from src.models.auth_user import AuthUser
from src.schemas.auth_system import AuthSystemCreate, AuthSystemUpdate, AuthSystemRead

router = APIRouter()


@router.get("/auth-systems", response_model=list[AuthSystemRead])
async def list_auth_systems(
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(AuthSystem)
        .where(AuthSystem.owner_id == admin.id)
        .order_by(AuthSystem.created_at.desc())
    )
    return result.scalars().all()


@router.post("/auth-systems", response_model=AuthSystemRead, status_code=201)
async def create_auth_system(
    data: AuthSystemCreate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    existing = await session.execute(
        select(AuthSystem.id).where(AuthSystem.slug == data.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Slug already exists")

    system = AuthSystem(
        owner_id=admin.id,
        name=data.name,
        slug=data.slug,
        access_token_ttl_minutes=data.access_token_ttl_minutes,
        refresh_token_ttl_days=data.refresh_token_ttl_days,
        registration_fields=[f.model_dump() for f in data.registration_fields],
        jwt_secret=secrets.token_urlsafe(48),
    )
    session.add(system)
    await session.commit()
    await session.refresh(system)
    return system


@router.get("/auth-systems/{system_id}", response_model=AuthSystemRead)
async def get_auth_system(
    system_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(AuthSystem).where(AuthSystem.id == system_id, AuthSystem.owner_id == admin.id)
    )
    system = result.scalar_one_or_none()
    if not system:
        raise HTTPException(status_code=404, detail="Auth system not found")
    return system


@router.put("/auth-systems/{system_id}", response_model=AuthSystemRead)
async def update_auth_system(
    system_id: uuid.UUID,
    data: AuthSystemUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(AuthSystem).where(AuthSystem.id == system_id, AuthSystem.owner_id == admin.id)
    )
    system = result.scalar_one_or_none()
    if not system:
        raise HTTPException(status_code=404, detail="Auth system not found")

    if data.slug is not None and data.slug != system.slug:
        existing = await session.execute(
            select(AuthSystem.id).where(AuthSystem.slug == data.slug, AuthSystem.id != system_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Slug already exists")

    for field in ("name", "slug", "access_token_ttl_minutes", "refresh_token_ttl_days", "users_active_by_default", "is_active"):
        val = getattr(data, field)
        if val is not None:
            setattr(system, field, val)

    if data.registration_fields is not None:
        system.registration_fields = [f.model_dump() for f in data.registration_fields]

    await session.commit()
    await session.refresh(system)
    return system


@router.delete("/auth-systems/{system_id}", status_code=204)
async def delete_auth_system(
    system_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(AuthSystem).where(AuthSystem.id == system_id, AuthSystem.owner_id == admin.id)
    )
    system = result.scalar_one_or_none()
    if not system:
        raise HTTPException(status_code=404, detail="Auth system not found")
    await session.delete(system)
    await session.commit()


@router.get("/auth-systems/{system_id}/users")
async def list_auth_system_users(
    system_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(AuthSystem.id).where(AuthSystem.id == system_id, AuthSystem.owner_id == admin.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Auth system not found")

    users_result = await session.execute(
        select(AuthUser)
        .where(AuthUser.auth_system_id == system_id)
        .order_by(AuthUser.created_at.desc())
    )
    users = users_result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "custom_fields": u.custom_fields,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.patch("/auth-systems/{system_id}/users/{user_id}/toggle")
async def toggle_auth_user(
    system_id: uuid.UUID,
    user_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(AuthSystem.id).where(AuthSystem.id == system_id, AuthSystem.owner_id == admin.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Auth system not found")

    user_result = await session.execute(
        select(AuthUser).where(AuthUser.id == user_id, AuthUser.auth_system_id == system_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = not user.is_active
    await session.commit()
    return {"id": str(user.id), "is_active": user.is_active}


@router.get("/auth-systems/{system_id}/stats")
async def auth_system_stats(
    system_id: uuid.UUID,
    hours: int = Query(default=720, ge=1, le=8760),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(AuthSystem.id).where(AuthSystem.id == system_id, AuthSystem.owner_id == admin.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Auth system not found")

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    base_filter = AuthUser.auth_system_id == system_id

    total_users = await session.scalar(select(func.count()).where(base_filter)) or 0
    active_users = await session.scalar(
        select(func.count()).where(base_filter, AuthUser.is_active == True)
    ) or 0
    new_users = await session.scalar(
        select(func.count()).where(base_filter, AuthUser.created_at >= since)
    ) or 0

    # Registrations timeseries
    if hours <= 168:
        bucket = "hour"
    else:
        bucket = "day"

    bucket_col = func.date_trunc(bucket, AuthUser.created_at).label("bucket")
    ts_result = await session.execute(
        select(bucket_col, func.count().label("count"))
        .where(base_filter, AuthUser.created_at >= since)
        .group_by(bucket_col)
        .order_by(bucket_col)
    )

    timeseries = [
        {"bucket": row.bucket.isoformat(), "count": row.count}
        for row in ts_result.all()
    ]

    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": total_users - active_users,
        "new_users": new_users,
        "timeseries": timeseries,
    }
