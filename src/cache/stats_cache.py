import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from src.cache.redis_client import get_redis

logger = logging.getLogger(__name__)

PREFIX = "proxyml:stats:"


async def cached_or_compute(
    key: str,
    ttl: int,
    compute: Callable[[], Awaitable[Any]],
) -> Any:
    full_key = PREFIX + key
    try:
        r = await get_redis()
        raw = await r.get(full_key)
        if raw is not None:
            return json.loads(raw)
    except Exception as e:
        logger.debug("stats cache get failed for %s: %s", key, e)

    value = await compute()

    try:
        r = await get_redis()
        await r.set(full_key, json.dumps(value, default=str), ex=ttl)
    except Exception as e:
        logger.debug("stats cache set failed for %s: %s", key, e)

    return value
