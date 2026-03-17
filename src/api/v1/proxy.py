import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_api_key_or_fail
from src.services.service_registry import get_service_by_slug, get_service_by_id
from src.proxy.base import registry
from src.proxy.handler import GenericProxyHandler  # ensure default is registered
from src.models.api_key import ApiKey

logger = logging.getLogger(__name__)
router = APIRouter()

@router.api_route("/{slug}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_request(
    slug: str,
    path: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    api_key: ApiKey = Depends(get_api_key_or_fail),
):
    # Check if api_key has access to this service
    if api_key.allowed_services and slug not in api_key.allowed_services:
        raise HTTPException(status_code=403, detail="API key does not have access to this service")

    service = await get_service_by_slug(session, slug)
    if not service or not service.is_active:
        raise HTTPException(status_code=404, detail="Service not found")

    # Multi-tenancy: API key must belong to the same owner as the service
    if api_key.owner_id and service.owner_id and api_key.owner_id != service.owner_id:
        raise HTTPException(status_code=403, detail="API key does not have access to this service")

    handler = registry.get(service.service_type)
    if handler is None:
        raise HTTPException(status_code=500, detail="No handler for service type")

    need_fallback = False
    response = None

    try:
        response = await handler.handle(request, service, path, api_key=api_key)
        fallback_statuses = service.fallback_on_statuses or []
        if fallback_statuses and response.status_code in fallback_statuses:
            need_fallback = True
    except Exception:
        need_fallback = True

    # Fallback to another service on failure
    if need_fallback and service.fallback_service_id:
        fallback_service = await get_service_by_id(session, service.fallback_service_id)
        if fallback_service and fallback_service.is_active:
            logger.info(f"Fallback: {service.slug} -> {fallback_service.slug}")
            fallback_handler = registry.get(fallback_service.service_type)
            if fallback_handler:
                return await fallback_handler.handle(
                    request, fallback_service, path, api_key=api_key,
                    is_fallback=True, fallback_from_slug=service.slug,
                )

    if response is None:
        raise HTTPException(status_code=502, detail="Service unavailable and no fallback configured")

    return response
