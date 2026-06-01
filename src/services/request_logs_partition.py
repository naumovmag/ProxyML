"""Daily maintenance for the partitioned request_logs table.

- Ensures partitions exist for today and a few days ahead.
- Drops partitions older than the retention window.

Runs as a background asyncio task started from the FastAPI lifespan.
"""
import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from src.config import settings
from src.db.engine import async_session_factory

logger = logging.getLogger(__name__)

PARTITION_PREFIX = "request_logs_"
RUN_INTERVAL_SECONDS = 6 * 3600  # every 6h: cheap, and survives missed runs


def _partition_name(d: datetime) -> str:
    return f"{PARTITION_PREFIX}{d.strftime('%Y%m%d')}"


async def ensure_partitions(ahead_days: int | None = None) -> int:
    """Create partitions for today and the next `ahead_days` days. Idempotent."""
    ahead_days = ahead_days if ahead_days is not None else settings.request_logs_partition_ahead_days
    created = 0
    today = datetime.now(UTC).date()
    async with async_session_factory() as session:
        for i in range(0, ahead_days + 1):
            day = today + timedelta(days=i)
            name = f"{PARTITION_PREFIX}{day.strftime('%Y%m%d')}"
            start = f"{day.isoformat()} 00:00:00+00"
            end = f"{(day + timedelta(days=1)).isoformat()} 00:00:00+00"
            await session.execute(text(
                f'CREATE TABLE IF NOT EXISTS "{name}" PARTITION OF request_logs '
                f"FOR VALUES FROM ('{start}') TO ('{end}')"
            ))
            created += 1
        await session.commit()
    return created


async def drop_old_partitions(retention_days: int | None = None) -> list[str]:
    """Drop partitions whose date range is fully older than retention. Returns dropped names."""
    retention_days = retention_days if retention_days is not None else settings.request_logs_retention_days
    cutoff = (datetime.now(UTC).date() - timedelta(days=retention_days)).strftime("%Y%m%d")
    dropped: list[str] = []
    async with async_session_factory() as session:
        result = await session.execute(text(
            "SELECT c.relname FROM pg_class c "
            "JOIN pg_inherits i ON i.inhrelid = c.oid "
            "JOIN pg_class p ON p.oid = i.inhparent "
            "WHERE p.relname = 'request_logs' AND c.relname LIKE :prefix"
        ), {"prefix": f"{PARTITION_PREFIX}%"})
        names = [row[0] for row in result.fetchall()]
        for name in names:
            suffix = name[len(PARTITION_PREFIX):]
            if len(suffix) == 8 and suffix.isdigit() and suffix < cutoff:
                await session.execute(text(f'DROP TABLE IF EXISTS "{name}"'))
                dropped.append(name)
        await session.commit()
    return dropped


async def run_maintenance() -> None:
    try:
        created = await ensure_partitions()
        dropped = await drop_old_partitions()
        logger.info(
            "request_logs partition maintenance: ensured=%d, dropped=%d (%s)",
            created, len(dropped), ", ".join(dropped) if dropped else "-",
        )
    except Exception as e:
        logger.exception("request_logs partition maintenance failed: %s", e)


_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


async def _loop() -> None:
    assert _stop_event is not None
    while not _stop_event.is_set():
        await run_maintenance()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(_stop_event.wait(), timeout=RUN_INTERVAL_SECONDS)


async def start() -> None:
    global _task, _stop_event
    if _task is not None:
        return
    _stop_event = asyncio.Event()
    _task = asyncio.create_task(_loop())
    logger.info(
        "request_logs partition scheduler started (retention=%dd, ahead=%dd, interval=%dh)",
        settings.request_logs_retention_days,
        settings.request_logs_partition_ahead_days,
        RUN_INTERVAL_SECONDS // 3600,
    )


async def stop() -> None:
    global _task, _stop_event
    if _task is None or _stop_event is None:
        return
    _stop_event.set()
    try:
        await asyncio.wait_for(_task, timeout=5)
    except TimeoutError:
        _task.cancel()
    _task = None
    _stop_event = None
