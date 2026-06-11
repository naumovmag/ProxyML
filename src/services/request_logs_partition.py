"""Daily maintenance for the partitioned request_logs table.

- Ensures partitions exist for today and a few days ahead.
- Drops partitions older than the retention window.
- Trims old load_test_results rows.

Runs as a background asyncio task started from the FastAPI lifespan.
All sessions use background_session_factory (NullPool) so maintenance never
competes with the request-path connection pool.
"""
import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta
from datetime import time as dt_time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.engine import background_session_factory

logger = logging.getLogger(__name__)

PARTITION_PREFIX = "request_logs_"
RUN_INTERVAL_SECONDS = 6 * 3600  # every 6h: cheap, and survives missed runs
DELETE_CHUNK = 5000


def _partition_name(d: datetime) -> str:
    return f"{PARTITION_PREFIX}{d.strftime('%Y%m%d')}"


async def ensure_partitions(ahead_days: int | None = None) -> int:
    """Create partitions for today and the next `ahead_days` days. Idempotent."""
    ahead_days = ahead_days if ahead_days is not None else settings.request_logs_partition_ahead_days
    created = 0
    today = datetime.now(UTC).date()
    async with background_session_factory() as session:
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


async def is_request_logs_partitioned(session: AsyncSession) -> bool:
    # relkind is the "char" type — asyncpg returns it as bytes, so cast to text
    relkind = await session.scalar(
        text("SELECT relkind::text FROM pg_class WHERE relname = 'request_logs'")
    )
    return relkind == "p"


async def drop_partitions_older_than(cutoff: datetime) -> list[str]:
    """Drop partitions whose entire day-range lies before cutoff. Returns dropped names.

    DROP TABLE on a partition is instant and returns disk space immediately,
    unlike DELETE which leaves dead tuples behind.
    """
    dropped: list[str] = []
    async with background_session_factory() as session:
        result = await session.execute(text(
            "SELECT c.relname FROM pg_class c "
            "JOIN pg_inherits i ON i.inhrelid = c.oid "
            "JOIN pg_class p ON p.oid = i.inhparent "
            "WHERE p.relname = 'request_logs' AND c.relname LIKE :prefix"
        ), {"prefix": f"{PARTITION_PREFIX}%"})
        names = [row[0] for row in result.fetchall()]
        for name in names:
            suffix = name[len(PARTITION_PREFIX):]
            if len(suffix) != 8 or not suffix.isdigit():
                continue
            day_start = datetime.strptime(suffix, "%Y%m%d").replace(tzinfo=UTC)
            if day_start + timedelta(days=1) <= cutoff:
                await session.execute(text(f'DROP TABLE IF EXISTS "{name}"'))
                dropped.append(name)
        await session.commit()
    return dropped


async def drop_old_partitions(retention_days: int | None = None) -> list[str]:
    """Drop partitions whose date range is fully older than retention. Returns dropped names."""
    retention_days = retention_days if retention_days is not None else settings.request_logs_retention_days
    midnight_today = datetime.combine(datetime.now(UTC).date(), dt_time.min, tzinfo=UTC)
    return await drop_partitions_older_than(midnight_today - timedelta(days=retention_days))


async def cleanup_old_load_test_results(retention_days: int | None = None) -> int:
    """Chunked delete of load_test_results older than retention. Returns deleted count."""
    retention_days = (
        retention_days if retention_days is not None else settings.load_test_results_retention_days
    )
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    total = 0
    async with background_session_factory() as session:
        while True:
            result = await session.execute(text(
                "DELETE FROM load_test_results WHERE id IN ("
                "SELECT id FROM load_test_results WHERE created_at < :cutoff "
                "ORDER BY created_at LIMIT :lim)"
            ), {"cutoff": cutoff, "lim": DELETE_CHUNK})
            await session.commit()
            n = result.rowcount or 0
            total += n
            if n < DELETE_CHUNK:
                break
            await asyncio.sleep(0.1)
    return total


async def run_maintenance() -> None:
    try:
        async with background_session_factory() as session:
            partitioned = await is_request_logs_partitioned(session)
        if partitioned:
            created = await ensure_partitions()
            dropped = await drop_old_partitions()
            logger.info(
                "request_logs partition maintenance: ensured=%d, dropped=%d (%s)",
                created, len(dropped), ", ".join(dropped) if dropped else "-",
            )
        else:
            logger.error(
                "request_logs is NOT partitioned — retention cleanup is disabled and the "
                "table will grow unbounded. Apply migration m3h4i5j6k7l8_partition_request_logs."
            )
    except Exception as e:
        logger.exception("request_logs partition maintenance failed: %s", e)

    try:
        deleted = await cleanup_old_load_test_results()
        if deleted:
            logger.info("load_test_results maintenance: deleted %d old rows", deleted)
    except Exception as e:
        logger.exception("load_test_results maintenance failed: %s", e)


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
