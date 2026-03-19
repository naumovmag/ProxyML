import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_current_admin
from src.models.request_log import RequestLog
from src.models.admin_user import AdminUser
from src.services.service_access import get_accessible_service_ids

router = APIRouter()


@router.get("/stats/overview")
async def stats_overview(
    hours: int = Query(default=24, ge=1, le=720),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Overall stats: total requests, avg duration, errors."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    svc_ids = await get_accessible_service_ids(session, admin.id)
    if not svc_ids:
        return {
            "period_hours": hours, "total_requests": 0, "total_errors": 0,
            "avg_duration_ms": 0, "total_request_bytes": 0, "total_response_bytes": 0,
        }
    access_filter = and_(RequestLog.created_at >= since, RequestLog.service_id.in_(svc_ids))

    total = await session.scalar(
        select(func.count()).where(access_filter)
    )
    errors = await session.scalar(
        select(func.count()).where(access_filter, RequestLog.status_code >= 400)
    )
    avg_duration = await session.scalar(
        select(func.avg(RequestLog.duration_ms)).where(access_filter)
    )
    total_request_bytes = await session.scalar(
        select(func.coalesce(func.sum(RequestLog.request_size), 0)).where(access_filter)
    )
    total_response_bytes = await session.scalar(
        select(func.coalesce(func.sum(RequestLog.response_size), 0)).where(access_filter)
    )

    return {
        "period_hours": hours,
        "total_requests": total or 0,
        "total_errors": errors or 0,
        "avg_duration_ms": round(avg_duration or 0, 1),
        "total_request_bytes": total_request_bytes or 0,
        "total_response_bytes": total_response_bytes or 0,
    }


@router.get("/stats/by-service")
async def stats_by_service(
    hours: int = Query(default=24, ge=1, le=720),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    svc_ids = await get_accessible_service_ids(session, admin.id)
    if not svc_ids:
        return []

    result = await session.execute(
        select(
            RequestLog.service_slug,
            func.count().label("request_count"),
            func.count().filter(RequestLog.status_code >= 400).label("error_count"),
            func.avg(RequestLog.duration_ms).label("avg_duration_ms"),
        )
        .where(RequestLog.created_at >= since, RequestLog.service_id.in_(svc_ids))
        .group_by(RequestLog.service_slug)
        .order_by(desc("request_count"))
    )

    return [
        {
            "service_slug": row.service_slug,
            "request_count": row.request_count,
            "error_count": row.error_count,
            "avg_duration_ms": round(row.avg_duration_ms or 0, 1),
        }
        for row in result.all()
    ]


@router.get("/stats/by-key")
async def stats_by_key(
    hours: int = Query(default=24, ge=1, le=720),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    svc_ids = await get_accessible_service_ids(session, admin.id)
    if not svc_ids:
        return []

    result = await session.execute(
        select(
            RequestLog.api_key_name,
            func.count().label("request_count"),
        )
        .where(
            RequestLog.created_at >= since,
            RequestLog.service_id.in_(svc_ids),
            RequestLog.api_key_name.isnot(None),
        )
        .group_by(RequestLog.api_key_name)
        .order_by(desc("request_count"))
    )

    return [
        {"api_key_name": row.api_key_name, "request_count": row.request_count}
        for row in result.all()
    ]


@router.get("/stats/recent")
async def stats_recent(
    limit: int = Query(default=50, ge=1, le=500),
    service_slug: str | None = Query(default=None),
    method: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    api_key_name: str | None = Query(default=None),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    svc_ids = await get_accessible_service_ids(session, admin.id)
    if not svc_ids:
        return []
    stmt = (
        select(RequestLog)
        .where(RequestLog.service_id.in_(svc_ids))
        .order_by(RequestLog.created_at.desc())
        .limit(limit)
    )
    if service_slug:
        stmt = stmt.where(RequestLog.service_slug == service_slug)
    if method:
        stmt = stmt.where(RequestLog.method == method.upper())
    if status == "ok":
        stmt = stmt.where(RequestLog.status_code < 400)
    elif status == "error":
        stmt = stmt.where(RequestLog.status_code >= 400)
    if source == "cache":
        stmt = stmt.where(RequestLog.is_cached == True)
    elif source == "origin":
        stmt = stmt.where(RequestLog.is_cached == False)
    if api_key_name:
        stmt = stmt.where(RequestLog.api_key_name == api_key_name)

    result = await session.execute(stmt)
    logs = result.scalars().all()

    return [
        {
            "id": str(log.id),
            "service_slug": log.service_slug,
            "api_key_name": log.api_key_name,
            "method": log.method,
            "path": log.path,
            "status_code": log.status_code,
            "duration_ms": log.duration_ms,
            "request_size": log.request_size,
            "response_size": log.response_size,
            "is_streaming": log.is_streaming,
            "is_cached": log.is_cached,
            "is_fallback": log.is_fallback,
            "fallback_from_slug": log.fallback_from_slug,
            "error": log.error,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
