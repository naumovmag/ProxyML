import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_admin
from src.cache.stats_cache import cached_or_compute
from src.db.session import get_async_session
from src.models.admin_user import AdminUser
from src.models.api_key import ApiKey
from src.models.request_log import RequestLog

router = APIRouter()


def _my_keys_subquery(admin_id: uuid.UUID):
    """Subquery selecting all ApiKey.id rows owned by this admin.

    Stats endpoints filter `RequestLog.api_key_id IN (...)` against this so
    each admin sees only requests issued via their own ApiKey — never traffic
    other admins generated against shared services.
    """
    return select(ApiKey.id).where(ApiKey.owner_id == admin_id).scalar_subquery()


@router.get("/stats/overview")
async def stats_overview(
    hours: int = Query(default=24, ge=1, le=720),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Overall stats: total requests, avg duration, errors."""

    async def _compute():
        since = datetime.now(UTC) - timedelta(hours=hours)
        access_filter = and_(
            RequestLog.created_at >= since,
            RequestLog.api_key_id.in_(_my_keys_subquery(admin.id)),
        )

        row = (
            await session.execute(
                select(
                    func.count().label("total"),
                    func.count().filter(RequestLog.status_code >= 400).label("errors"),
                    func.avg(RequestLog.duration_ms).label("avg_duration_ms"),
                    func.coalesce(func.sum(RequestLog.request_size), 0).label("req_bytes"),
                    func.coalesce(func.sum(RequestLog.response_size), 0).label("resp_bytes"),
                ).where(access_filter)
            )
        ).one()

        return {
            "period_hours": hours,
            "total_requests": row.total or 0,
            "total_errors": row.errors or 0,
            "avg_duration_ms": round(row.avg_duration_ms or 0, 1),
            "total_request_bytes": row.req_bytes or 0,
            "total_response_bytes": row.resp_bytes or 0,
        }

    return await cached_or_compute(f"overview:{admin.id}:{hours}", ttl=30, compute=_compute)


@router.get("/stats/by-service")
async def stats_by_service(
    hours: int = Query(default=24, ge=1, le=720),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    async def _compute():
        since = datetime.now(UTC) - timedelta(hours=hours)
        access_filter = and_(
            RequestLog.created_at >= since,
            RequestLog.api_key_id.in_(_my_keys_subquery(admin.id)),
        )

        result = await session.execute(
            select(
                RequestLog.service_slug,
                func.count().label("request_count"),
                func.count().filter(RequestLog.status_code >= 400).label("error_count"),
                func.avg(RequestLog.duration_ms).label("avg_duration_ms"),
            )
            .where(access_filter)
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

    return await cached_or_compute(f"by-service:{admin.id}:{hours}", ttl=60, compute=_compute)


@router.get("/stats/by-key")
async def stats_by_key(
    hours: int = Query(default=24, ge=1, le=720),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    async def _compute():
        since = datetime.now(UTC) - timedelta(hours=hours)
        access_filter = and_(
            RequestLog.created_at >= since,
            RequestLog.api_key_id.in_(_my_keys_subquery(admin.id)),
        )

        result = await session.execute(
            select(
                RequestLog.api_key_id,
                RequestLog.api_key_name,
                func.count().label("request_count"),
                func.count().filter(RequestLog.status_code >= 400).label("error_count"),
                func.avg(RequestLog.duration_ms).label("avg_duration_ms"),
            )
            .where(access_filter)
            .group_by(RequestLog.api_key_id, RequestLog.api_key_name)
            .order_by(desc("request_count"))
        )

        return [
            {
                "api_key_id": str(row.api_key_id),
                "api_key_name": row.api_key_name,
                "request_count": row.request_count,
                "error_count": row.error_count,
                "avg_duration_ms": round(row.avg_duration_ms or 0, 1),
            }
            for row in result.all()
        ]

    return await cached_or_compute(f"by-key:{admin.id}:{hours}", ttl=60, compute=_compute)


@router.get("/stats/timeseries")
async def stats_timeseries(
    hours: int = Query(default=24, ge=1, le=720),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    async def _compute():
        since = datetime.now(UTC) - timedelta(hours=hours)
        access_filter = and_(
            RequestLog.created_at >= since,
            RequestLog.api_key_id.in_(_my_keys_subquery(admin.id)),
        )

        if hours <= 6:
            bucket = "minute"
        elif hours <= 168:
            bucket = "hour"
        else:
            bucket = "day"

        bucket_col = func.date_trunc(bucket, RequestLog.created_at).label("bucket")

        result = await session.execute(
            select(
                bucket_col,
                func.count().label("total"),
                func.count().filter(RequestLog.status_code < 400).label("success"),
                func.count().filter(RequestLog.status_code >= 400).label("errors"),
                func.avg(RequestLog.duration_ms).label("avg_duration_ms"),
            )
            .where(access_filter)
            .group_by(bucket_col)
            .order_by(bucket_col)
        )

        return [
            {
                "bucket": row.bucket.isoformat(),
                "total": row.total,
                "success": row.success,
                "errors": row.errors,
                "avg_duration_ms": round(row.avg_duration_ms or 0, 1),
            }
            for row in result.all()
        ]

    ttl = 30 if hours <= 6 else (60 if hours <= 168 else 300)
    return await cached_or_compute(f"timeseries:{admin.id}:{hours}", ttl=ttl, compute=_compute)


@router.get("/stats/status-breakdown")
async def stats_status_breakdown(
    hours: int = Query(default=24, ge=1, le=720),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    async def _compute():
        since = datetime.now(UTC) - timedelta(hours=hours)
        access_filter = and_(
            RequestLog.created_at >= since,
            RequestLog.api_key_id.in_(_my_keys_subquery(admin.id)),
        )

        group_col = case(
            (RequestLog.status_code < 200, "1xx"),
            (RequestLog.status_code < 300, "2xx"),
            (RequestLog.status_code < 400, "3xx"),
            (RequestLog.status_code < 500, "4xx"),
            else_="5xx",
        ).label("status_group")

        result = await session.execute(
            select(group_col, func.count().label("count"))
            .where(access_filter)
            .group_by(group_col)
            .order_by(group_col)
        )

        return [
            {"group": row.status_group, "count": row.count}
            for row in result.all()
        ]

    return await cached_or_compute(
        f"status-breakdown:{admin.id}:{hours}", ttl=60, compute=_compute
    )


@router.get("/stats/cache-savings")
async def stats_cache_savings(
    hours: int = Query(default=24, ge=1, le=720),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Estimated time saved by cache hits over the given period."""

    async def _compute():
        since = datetime.now(UTC) - timedelta(hours=hours)
        base = and_(
            RequestLog.created_at >= since,
            RequestLog.api_key_id.in_(_my_keys_subquery(admin.id)),
        )

        origin_avg = (
            select(
                RequestLog.service_id.label("service_id"),
                RequestLog.method.label("method"),
                RequestLog.path.label("path"),
                func.avg(RequestLog.duration_ms).label("avg_ms"),
            )
            .where(base, RequestLog.is_cached == False, RequestLog.status_code < 400)
            .group_by(RequestLog.service_id, RequestLog.method, RequestLog.path)
            .subquery()
        )

        cache_agg = (
            select(
                RequestLog.service_id.label("service_id"),
                RequestLog.method.label("method"),
                RequestLog.path.label("path"),
                func.count().label("cache_count"),
                func.coalesce(func.sum(RequestLog.duration_ms), 0.0).label("sum_cache_ms"),
            )
            .where(base, RequestLog.is_cached == True)
            .group_by(RequestLog.service_id, RequestLog.method, RequestLog.path)
            .subquery()
        )

        saved_expr = func.greatest(
            cache_agg.c.cache_count * origin_avg.c.avg_ms - cache_agg.c.sum_cache_ms,
            0.0,
        )

        total_saved = await session.scalar(
            select(func.coalesce(func.sum(saved_expr), 0.0)).select_from(
                cache_agg.join(
                    origin_avg,
                    and_(
                        cache_agg.c.service_id == origin_avg.c.service_id,
                        cache_agg.c.method == origin_avg.c.method,
                        cache_agg.c.path == origin_avg.c.path,
                    ),
                )
            )
        )

        counts = (
            await session.execute(
                select(
                    func.count().filter(RequestLog.is_cached == True).label("hits"),
                    func.count().filter(RequestLog.is_cached == False).label("misses"),
                ).where(base)
            )
        ).one()

        return {
            "period_hours": hours,
            "total_saved_ms": round(float(total_saved or 0), 1),
            "cache_hit_count": counts.hits or 0,
            "cache_miss_count": counts.misses or 0,
        }

    return await cached_or_compute(
        f"cache-savings:{admin.id}:{hours}", ttl=120, compute=_compute
    )


@router.get("/stats/recent")
async def stats_recent(
    limit: int = Query(default=50, ge=1, le=200),
    service_slug: str | None = Query(default=None),
    method: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    api_key_name: str | None = Query(default=None),
    api_key_id: str | None = Query(default=None),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    stmt = (
        select(RequestLog)
        .where(RequestLog.api_key_id.in_(_my_keys_subquery(admin.id)))
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
    if api_key_id:
        stmt = stmt.where(RequestLog.api_key_id == uuid.UUID(api_key_id))

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
