import hashlib
import json
import logging
from src.cache.redis_client import get_redis
from src.config import settings

logger = logging.getLogger(__name__)

CACHE_PREFIX = "proxyml:cache:"


def _build_cache_key(slug: str, method: str, path: str, query: str, body: bytes) -> str:
    """Build a deterministic cache key from request parameters."""
    raw = f"{slug}:{method}:{path}:{query}:{body.hex()}"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"{CACHE_PREFIX}{slug}:{method}:{digest}"


async def get_cached_response(
    slug: str, method: str, path: str, query: str, body: bytes,
) -> dict | None:
    """Return cached response dict or None."""
    try:
        r = await get_redis()
        key = _build_cache_key(slug, method, path, query, body)
        data = await r.get(key)
        if data is None:
            return None
        return json.loads(data)
    except Exception as e:
        logger.debug(f"Cache get error: {e}")
        return None


async def set_cached_response(
    slug: str, method: str, path: str, query: str, body: bytes,
    status_code: int, headers: dict, content: bytes,
    ttl: int | None = None,
) -> None:
    """Cache a successful response."""
    try:
        r = await get_redis()
        key = _build_cache_key(slug, method, path, query, body)
        payload = json.dumps({
            "status_code": status_code,
            "headers": headers,
            "content": content.hex(),
        })
        await r.set(key, payload, ex=ttl or settings.cache_ttl_seconds)
    except Exception as e:
        logger.debug(f"Cache set error: {e}")
