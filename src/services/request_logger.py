import asyncio
import logging
import uuid
from src.db.engine import async_session_factory
from src.models.request_log import RequestLog

logger = logging.getLogger(__name__)


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
    error: str | None = None,
) -> None:
    """Fire-and-forget: schedule DB write without awaiting it in the request path."""
    asyncio.get_running_loop().create_task(
        _write_log(
            service_id=service_id,
            service_slug=service_slug,
            api_key_id=api_key_id,
            api_key_name=api_key_name,
            method=method,
            path=path,
            status_code=status_code,
            request_size=request_size,
            response_size=response_size,
            duration_ms=duration_ms,
            is_streaming=is_streaming,
            is_cached=is_cached,
            error=error,
        )
    )


async def _write_log(**kwargs) -> None:
    try:
        async with async_session_factory() as session:
            session.add(RequestLog(**kwargs))
            await session.commit()
    except Exception as e:
        logger.warning(f"Failed to write request log: {e}")
