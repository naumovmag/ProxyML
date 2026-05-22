from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_superadmin
from src.db.engine import background_session_factory, engine
from src.db.session import get_async_session
from src.models.admin_user import AdminUser
from src.models.load_test import LoadTestResult
from src.models.request_log import RequestLog

router = APIRouter()

CHUNK_SIZE = 5000

_TABLES = {
    "request_logs": RequestLog,
    "load_test_results": LoadTestResult,
}


class CleanupRequest(BaseModel):
    retention_hours: int = Field(ge=1, le=8760)
    tables: list[str] = Field(default_factory=lambda: list(_TABLES.keys()))


def _validate_tables(tables: list[str]) -> list[str]:
    return [t for t in tables if t in _TABLES]


async def _count_old(session: AsyncSession, model, cutoff: datetime) -> int:
    return (
        await session.scalar(
            select(func.count()).select_from(model).where(model.created_at < cutoff)
        )
    ) or 0


async def _delete_chunked(session: AsyncSession, model, cutoff: datetime) -> int:
    """Delete rows older than cutoff in chunks to avoid long-running locks."""
    total_deleted = 0
    while True:
        ids_subq = (
            select(model.id).where(model.created_at < cutoff).limit(CHUNK_SIZE)
        ).scalar_subquery()
        result = await session.execute(
            delete(model).where(model.id.in_(ids_subq))
        )
        affected = result.rowcount or 0
        await session.commit()
        total_deleted += affected
        if affected < CHUNK_SIZE:
            break
    return total_deleted


@router.get("/maintenance/pool-stats")
async def maintenance_pool_stats(
    _admin: AdminUser = Depends(get_current_superadmin),
):
    """Live SQLAlchemy connection-pool snapshot for capacity diagnostics."""
    pool = engine.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "configured_pool_size": engine.pool._pool.maxsize if hasattr(engine.pool, "_pool") else None,
    }


@router.get("/maintenance/cleanup-preview")
async def maintenance_preview(
    retention_hours: int = Query(ge=1, le=8760),
    _admin: AdminUser = Depends(get_current_superadmin),
    session: AsyncSession = Depends(get_async_session),
):
    cutoff = datetime.now(UTC) - timedelta(hours=retention_hours)
    counts: dict[str, int] = {}
    for name, model in _TABLES.items():
        counts[name] = await _count_old(session, model, cutoff)
    return {
        "retention_hours": retention_hours,
        "cutoff": cutoff.isoformat(),
        "counts": counts,
    }


@router.post("/maintenance/cleanup")
async def maintenance_cleanup(
    data: CleanupRequest,
    _admin: AdminUser = Depends(get_current_superadmin),
):
    # Use background_session_factory (NullPool) so the long chunked DELETE does not
    # hold a connection from the request-path pool and starve admin/proxy endpoints.
    tables = _validate_tables(data.tables)
    cutoff = datetime.now(UTC) - timedelta(hours=data.retention_hours)
    deleted: dict[str, int] = {}
    async with background_session_factory() as session:
        for name in tables:
            deleted[name] = await _delete_chunked(session, _TABLES[name], cutoff)
    return {
        "retention_hours": data.retention_hours,
        "cutoff": cutoff.isoformat(),
        "deleted": deleted,
    }
