import redis.asyncio as redis

from src.config import settings

_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.from_url(
            settings.redis_url,
            decode_responses=False,
            max_connections=50,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
            health_check_interval=30,
            retry_on_timeout=False,
        )
    return _pool


async def close_redis():
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
