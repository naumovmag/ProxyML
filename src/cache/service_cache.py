import logging
import pickle
import uuid

from src.cache.redis_client import get_redis
from src.models.service import Service

logger = logging.getLogger(__name__)

_KEY_BY_SLUG = "proxyml:svc:slug:{}"
_KEY_BY_ID = "proxyml:svc:id:{}"
_TTL_SECONDS = 300


async def cache_get_by_slug(slug: str) -> Service | None:
    try:
        r = await get_redis()
        raw = await r.get(_KEY_BY_SLUG.format(slug))
        if raw is None:
            return None
        return pickle.loads(raw)
    except Exception as e:
        logger.debug("service cache get_by_slug failed for %s: %s", slug, e)
        return None


async def cache_get_by_id(service_id: uuid.UUID) -> Service | None:
    try:
        r = await get_redis()
        raw = await r.get(_KEY_BY_ID.format(service_id))
        if raw is None:
            return None
        return pickle.loads(raw)
    except Exception as e:
        logger.debug("service cache get_by_id failed for %s: %s", service_id, e)
        return None


async def cache_set(service: Service) -> None:
    try:
        r = await get_redis()
        blob = pickle.dumps(service)
        await r.set(_KEY_BY_SLUG.format(service.slug), blob, ex=_TTL_SECONDS)
        await r.set(_KEY_BY_ID.format(service.id), blob, ex=_TTL_SECONDS)
    except Exception as e:
        logger.debug("service cache set failed for %s: %s", service.slug, e)


async def cache_invalidate(slug: str | None, service_id: uuid.UUID | None) -> None:
    try:
        r = await get_redis()
        keys = []
        if slug:
            keys.append(_KEY_BY_SLUG.format(slug))
        if service_id:
            keys.append(_KEY_BY_ID.format(service_id))
        if keys:
            await r.delete(*keys)
    except Exception as e:
        logger.debug("service cache invalidate failed: %s", e)
