from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_api_key_or_fail
from src.services.service_registry import get_service_by_slug
from src.proxy.base import registry
from src.proxy.handler import GenericProxyHandler  # ensure default is registered
from src.models.api_key import ApiKey

router = APIRouter()

@router.api_route("/proxy/{slug}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
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

    handler = registry.get(service.service_type)
    if handler is None:
        raise HTTPException(status_code=500, detail="No handler for service type")

    return await handler.handle(request, service, path)
