import asyncio
import contextlib
import logging
import uuid
from collections import deque
from typing import Any

from sqlalchemy import insert

from src.db.engine import background_session_factory
from src.models.request_log import RequestLog

logger = logging.getLogger(__name__)

MAX_BATCH = 1000
MAX_INTERVAL_SECONDS = 2.0
MAX_BUFFER = 10000
MAX_FLUSH_RETRIES = 5  # drop the batch after this many consecutive failures

_buffer: deque[dict[str, Any]] = deque()
_flush_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None
_wake_event: asyncio.Event | None = None
_dropped_total = 0


def log_request_fire_and_forget(
    *,
    service_id: uuid.UUID,
    service_slug: str,
    api_key_id: uuid.UUID | None,
    api_key_name: str | None,
    method: str,
    path: str,
    status_code: int,
    request_size: int,
    response_size: int,
    duration_ms: float,
    is_streaming: bool,
    is_cached: bool = False,
    is_fallback: bool = False,
    fallback_from_slug: str | None = None,
    error: str | None = None,
    owner_id: uuid.UUID | None = None,
) -> None:
    """Non-blocking: append row to in-memory buffer; background loop flushes in batches."""
    global _dropped_total

    if len(_buffer) >= MAX_BUFFER:
        _buffer.popleft()
        _dropped_total += 1
        if _dropped_total % 100 == 1:
            logger.warning("request_logger buffer full, dropped %d records total", _dropped_total)

    _buffer.append({
        "service_id": service_id,
        "service_slug": service_slug,
        "api_key_id": api_key_id,
        "api_key_name": api_key_name,
        "method": method,
        "path": path,
        "status_code": status_code,
        "request_size": request_size,
        "response_size": response_size,
        "duration_ms": duration_ms,
        "is_streaming": is_streaming,
        "is_cached": is_cached,
        "is_fallback": is_fallback,
        "fallback_from_slug": fallback_from_slug,
        "error": error,
        "owner_id": owner_id,
    })

    if len(_buffer) >= MAX_BATCH and _wake_event is not None:
        _wake_event.set()


async def _flush_batch(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return True
    try:
        async with background_session_factory() as session:
            await session.execute(insert(RequestLog), rows)
            await session.commit()
        return True
    except Exception as e:
        logger.warning("request_logger flush failed for %d rows: %r", len(rows), e)
        return False


async def _flush_loop() -> None:
    assert _stop_event is not None and _wake_event is not None
    consecutive_failures = 0
    while not _stop_event.is_set():
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(_wake_event.wait(), timeout=MAX_INTERVAL_SECONDS)
        _wake_event.clear()

        if not _buffer:
            continue

        take = min(len(_buffer), MAX_BATCH)
        rows = [_buffer.popleft() for _ in range(take)]
        ok = await _flush_batch(rows)
        if ok:
            consecutive_failures = 0
            continue

        consecutive_failures += 1
        if consecutive_failures >= MAX_FLUSH_RETRIES:
            logger.error(
                "request_logger: dropping poison batch of %d rows after %d failed attempts",
                len(rows), consecutive_failures,
            )
            consecutive_failures = 0
        else:
            for row in reversed(rows):
                _buffer.appendleft(row)
            await asyncio.sleep(1.0)

    # Drain remainder on shutdown
    while _buffer:
        take = min(len(_buffer), MAX_BATCH)
        rows = [_buffer.popleft() for _ in range(take)]
        ok = await _flush_batch(rows)
        if not ok:
            logger.error("request_logger: lost %d rows on shutdown", len(rows))
            break


async def start_request_logger() -> None:
    global _flush_task, _stop_event, _wake_event
    if _flush_task is not None:
        return
    _stop_event = asyncio.Event()
    _wake_event = asyncio.Event()
    _flush_task = asyncio.create_task(_flush_loop())
    logger.info("request_logger started (batch=%d, interval=%.1fs)", MAX_BATCH, MAX_INTERVAL_SECONDS)


async def stop_request_logger() -> None:
    global _flush_task, _stop_event, _wake_event
    if _flush_task is None or _stop_event is None or _wake_event is None:
        return
    pending = len(_buffer)
    if pending:
        logger.info("request_logger: flushing remaining %d rows on shutdown", pending)
    _stop_event.set()
    _wake_event.set()
    try:
        await asyncio.wait_for(_flush_task, timeout=15.0)
    except TimeoutError:
        logger.warning("request_logger: flush did not finish within timeout")
    _flush_task = None
    _stop_event = None
    _wake_event = None
