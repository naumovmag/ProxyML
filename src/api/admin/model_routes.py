import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_admin
from src.db.session import get_async_session
from src.models.admin_user import AdminUser
from src.models.model_route import ModelRoute
from src.models.service import Service
from src.proxy.client import get_http_client
from src.schemas.model_route import ModelRouteCreate, ModelRouteRead, ModelRouteUpdate
from src.services.service_access import check_service_access

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_owned_service(
    service_id: uuid.UUID, admin: AdminUser, session: AsyncSession
) -> Service:
    svc, role = await check_service_access(session, service_id, admin.id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    if role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can manage model routes")
    if svc.service_type != "unified_llm":
        raise HTTPException(status_code=400, detail="Model routes are only for unified_llm services")
    return svc


def _route_to_read(route: ModelRoute, target: Service | None = None) -> ModelRouteRead:
    return ModelRouteRead(
        id=route.id,
        service_id=route.service_id,
        model_pattern=route.model_pattern,
        target_service_id=route.target_service_id,
        target_service_name=target.name if target else None,
        target_service_slug=target.slug if target else None,
        priority=route.priority,
        override_model=route.override_model,
        created_at=route.created_at,
    )


@router.get("/services/{service_id}/model-routes", response_model=list[ModelRouteRead])
async def list_model_routes(
    service_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_owned_service(service_id, admin, session)

    result = await session.execute(
        select(ModelRoute, Service)
        .outerjoin(Service, Service.id == ModelRoute.target_service_id)
        .where(ModelRoute.service_id == service_id)
        .order_by(ModelRoute.priority, ModelRoute.created_at)
    )
    return [_route_to_read(route, target) for route, target in result.all()]


@router.post("/services/{service_id}/model-routes", response_model=ModelRouteRead, status_code=201)
async def create_model_route(
    service_id: uuid.UUID,
    data: ModelRouteCreate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_owned_service(service_id, admin, session)

    # Validate target service exists and is llm_chat type
    target = await session.get(Service, data.target_service_id)
    if not target:
        raise HTTPException(status_code=400, detail="Target service not found")
    if target.service_type == "unified_llm":
        raise HTTPException(status_code=400, detail="Target cannot be another unified_llm service")

    # Check for duplicate pattern
    existing = await session.execute(
        select(ModelRoute.id).where(
            ModelRoute.service_id == service_id,
            ModelRoute.model_pattern == data.model_pattern,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Route for model '{data.model_pattern}' already exists")

    route = ModelRoute(
        service_id=service_id,
        model_pattern=data.model_pattern,
        target_service_id=data.target_service_id,
        priority=data.priority,
        override_model=data.override_model,
    )
    session.add(route)
    await session.commit()
    await session.refresh(route)
    return _route_to_read(route, target)


@router.put("/services/{service_id}/model-routes/{route_id}", response_model=ModelRouteRead)
async def update_model_route(
    service_id: uuid.UUID,
    route_id: uuid.UUID,
    data: ModelRouteUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_owned_service(service_id, admin, session)

    result = await session.execute(
        select(ModelRoute).where(ModelRoute.id == route_id, ModelRoute.service_id == service_id)
    )
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    if data.target_service_id is not None:
        target = await session.get(Service, data.target_service_id)
        if not target:
            raise HTTPException(status_code=400, detail="Target service not found")
        if target.service_type == "unified_llm":
            raise HTTPException(status_code=400, detail="Target cannot be another unified_llm service")
        route.target_service_id = data.target_service_id

    if data.model_pattern is not None:
        # Check duplicate
        existing = await session.execute(
            select(ModelRoute.id).where(
                ModelRoute.service_id == service_id,
                ModelRoute.model_pattern == data.model_pattern,
                ModelRoute.id != route_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Route for model '{data.model_pattern}' already exists")
        route.model_pattern = data.model_pattern

    if data.priority is not None:
        route.priority = data.priority
    if data.override_model is not None:
        route.override_model = data.override_model or None

    await session.commit()
    await session.refresh(route)

    target = await session.get(Service, route.target_service_id)
    return _route_to_read(route, target)


@router.delete("/services/{service_id}/model-routes/{route_id}", status_code=204)
async def delete_model_route(
    service_id: uuid.UUID,
    route_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_owned_service(service_id, admin, session)

    result = await session.execute(
        select(ModelRoute).where(ModelRoute.id == route_id, ModelRoute.service_id == service_id)
    )
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    await session.delete(route)
    await session.commit()


@router.get("/services/{service_id}/available-models")
async def list_available_models(
    service_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Fetch /v1/models from a service's backend and return model IDs."""
    svc, _role = await check_service_access(session, service_id, admin.id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    # Build URL
    url = f"{svc.base_url.rstrip('/')}/v1/models"
    headers: dict[str, str] = {}
    if svc.auth_type == "bearer":
        headers["Authorization"] = f"Bearer {svc.auth_token}"
    elif svc.auth_type == "header":
        headers[svc.auth_header_name or "Authorization"] = svc.auth_token or ""
    if svc.extra_headers:
        headers.update(svc.extra_headers)

    try:
        client = await get_http_client()
        resp = await client.get(url, headers=headers, timeout=10.0)
        if resp.status_code != 200:
            return {"models": [], "error": f"Backend returned {resp.status_code}"}
        data = resp.json()
        models = [m.get("id", m.get("name", "")) for m in data.get("data", [])]
        return {"models": models}
    except Exception as e:
        logger.warning(f"Failed to fetch models from {svc.slug}: {e}")
        return {"models": [], "error": str(e)}
