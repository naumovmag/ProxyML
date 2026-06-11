import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_superadmin
from src.db.engine import background_session_factory, engine
from src.db.session import get_async_session
from src.models.admin_user import AdminUser
from src.services.request_logs_partition import (
    drop_partitions_older_than,
    is_request_logs_partitioned,
)

logger = logging.getLogger(__name__)
router = APIRouter()

CHUNK_SIZE = 5000
PREVIEW_TIMEOUT_MS = 10_000

_TABLES = ("request_logs", "load_test_results")

# Single-flight state for the background cleanup job. The chunked DELETE over
# millions of rows can run for a long time, so the endpoint returns immediately
# and the UI polls /maintenance/cleanup-status.
_cleanup_state: dict[str, Any] = {"status": "idle"}
_cleanup_task: asyncio.Task | None = None


class CleanupRequest(BaseModel):
    retention_hours: int = Field(ge=1, le=8760)
    tables: list[str] = Field(default_factory=lambda: list(_TABLES))


def _validate_tables(tables: list[str]) -> list[str]:
    return [t for t in tables if t in _TABLES]


async def _approx_total(session: AsyncSession, table: str) -> int:
    """Planner estimate of total rows in table (including partitions)."""
    val = await session.scalar(text(
        "SELECT COALESCE(SUM(GREATEST(c.reltuples, 0)), 0) FROM pg_class c "
        "WHERE c.relname = :t OR c.oid IN ("
        "  SELECT i.inhrelid FROM pg_inherits i "
        "  JOIN pg_class p ON p.oid = i.inhparent WHERE p.relname = :t)"
    ), {"t": table})
    return int(val or 0)


async def _count_old(session: AsyncSession, table: str, cutoff: datetime) -> tuple[int, bool]:
    """Exact count of rows older than cutoff, capped at PREVIEW_TIMEOUT_MS.

    On timeout falls back to the planner's total-row estimate (not cutoff-aware)
    so the preview never hangs on a bloated table. Returns (count, approximate).
    """
    try:
        await session.execute(text(f"SET LOCAL statement_timeout = '{PREVIEW_TIMEOUT_MS}'"))
        n = await session.scalar(
            text(f'SELECT count(*) FROM "{table}" WHERE created_at < :cutoff'),
            {"cutoff": cutoff},
        )
        return int(n or 0), False
    except Exception:
        await session.rollback()
        return await _approx_total(session, table), True


async def _delete_chunked(table: str, cutoff: datetime) -> int:
    """Delete rows older than cutoff in chunks to avoid long-running locks."""
    total = 0
    async with background_session_factory() as session:
        while True:
            result = await session.execute(text(
                f'DELETE FROM "{table}" WHERE id IN ('
                f'SELECT id FROM "{table}" WHERE created_at < :cutoff '
                f"ORDER BY created_at LIMIT :lim)"
            ), {"cutoff": cutoff, "lim": CHUNK_SIZE})
            await session.commit()
            n = result.rowcount or 0
            total += n
            _cleanup_state["deleted"][table] = total
            if n < CHUNK_SIZE:
                break
            await asyncio.sleep(0.1)
    return total


async def _run_cleanup(cutoff: datetime, tables: list[str]) -> None:
    try:
        if "request_logs" in tables:
            async with background_session_factory() as session:
                partitioned = await is_request_logs_partitioned(session)
            if partitioned:
                # Whole-day partitions older than cutoff are dropped instantly
                # (returns disk space); only the boundary day needs row deletes.
                dropped = await drop_partitions_older_than(cutoff)
                _cleanup_state["dropped_partitions"] = dropped
            await _delete_chunked("request_logs", cutoff)
        if "load_test_results" in tables:
            await _delete_chunked("load_test_results", cutoff)
        _cleanup_state["status"] = "done"
    except Exception as e:
        logger.exception("maintenance cleanup failed")
        _cleanup_state["status"] = "error"
        _cleanup_state["error"] = str(e)
    finally:
        _cleanup_state["finished_at"] = datetime.now(UTC).isoformat()


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
    approximate: dict[str, bool] = {}
    for name in _TABLES:
        counts[name], approximate[name] = await _count_old(session, name, cutoff)
    return {
        "retention_hours": retention_hours,
        "cutoff": cutoff.isoformat(),
        "counts": counts,
        "approximate": approximate,
    }


@router.get("/maintenance/cleanup-status")
async def maintenance_cleanup_status(
    _admin: AdminUser = Depends(get_current_superadmin),
):
    return _cleanup_state


@router.post("/maintenance/cleanup", status_code=202)
async def maintenance_cleanup(
    data: CleanupRequest,
    _admin: AdminUser = Depends(get_current_superadmin),
):
    global _cleanup_task
    if _cleanup_task is not None and not _cleanup_task.done():
        raise HTTPException(status_code=409, detail="Cleanup is already running")

    tables = _validate_tables(data.tables)
    cutoff = datetime.now(UTC) - timedelta(hours=data.retention_hours)
    _cleanup_state.clear()
    _cleanup_state.update({
        "status": "running",
        "retention_hours": data.retention_hours,
        "cutoff": cutoff.isoformat(),
        "tables": tables,
        "deleted": dict.fromkeys(tables, 0),
        "dropped_partitions": [],
        "started_at": datetime.now(UTC).isoformat(),
    })
    _cleanup_task = asyncio.create_task(_run_cleanup(cutoff, tables))
    return {"status": "started", "cutoff": cutoff.isoformat(), "tables": tables}
