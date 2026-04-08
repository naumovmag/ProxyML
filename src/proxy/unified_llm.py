import json
import logging

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.api_key import ApiKey
from src.models.model_route import ModelRoute
from src.models.service import Service
from src.proxy.base import AbstractProxyHandler, registry
from src.proxy.handler import GenericProxyHandler

logger = logging.getLogger(__name__)

_generic = GenericProxyHandler()


class UnifiedLLMHandler(AbstractProxyHandler):
    async def handle(
        self,
        request: Request,
        service: Service,
        path: str,
        api_key: ApiKey | None = None,
        is_fallback: bool = False,
        fallback_from_slug: str | None = None,
    ) -> Response:
        session: AsyncSession = request.state.db_session

        # Special case: /v1/models — aggregate models from all target services
        if path.rstrip("/") == "v1/models":
            return await self._handle_models(session, service)

        # Parse body to extract "model" field
        body = await request.body()
        model_name = None
        if body:
            try:
                body_json = json.loads(body)
                model_name = body_json.get("model")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        # Resolve target service via model_routes
        target_service, override_model = await self._resolve_target(
            session, service.id, model_name
        )
        if target_service is None:
            available = await self._get_available_models(session, service.id)
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": f"Model '{model_name}' not found in unified service '{service.slug}'. Available models: {available}",
                        "type": "invalid_request_error",
                        "code": "model_not_found",
                    }
                },
            )

        # If override_model is set, patch the body
        if override_model and body and model_name:
            try:
                body_json = json.loads(body)
                body_json["model"] = override_model
                patched_body = json.dumps(body_json).encode()
                # Replace cached body on request
                request._body = patched_body
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        logger.info(
            f"Unified route: {service.slug} model={model_name} -> {target_service.slug}"
        )

        return await _generic.handle(
            request,
            target_service,
            path,
            api_key=api_key,
            is_fallback=is_fallback,
            fallback_from_slug=fallback_from_slug,
        )

    async def _resolve_target(
        self,
        session: AsyncSession,
        service_id,
        model_name: str | None,
    ) -> tuple[Service | None, str | None]:
        """Find target service for a given model name."""
        result = await session.execute(
            select(ModelRoute)
            .where(ModelRoute.service_id == service_id)
            .order_by(ModelRoute.priority)
        )
        routes = result.scalars().all()

        default_route = None
        for route in routes:
            if route.model_pattern == "*":
                default_route = route
                continue
            if model_name and route.model_pattern == model_name:
                target = await session.get(Service, route.target_service_id)
                if target and target.is_active:
                    return target, route.override_model
                break

        # Fall back to default route
        if default_route:
            target = await session.get(Service, default_route.target_service_id)
            if target and target.is_active:
                return target, default_route.override_model

        return None, None

    async def _get_available_models(
        self, session: AsyncSession, service_id
    ) -> list[str]:
        result = await session.execute(
            select(ModelRoute.model_pattern)
            .where(ModelRoute.service_id == service_id)
            .where(ModelRoute.model_pattern != "*")
            .order_by(ModelRoute.priority)
        )
        return list(result.scalars().all())

    async def _handle_models(
        self, session: AsyncSession, service: Service
    ) -> JSONResponse:
        """Return public model names from model_routes."""
        result = await session.execute(
            select(ModelRoute, Service)
            .join(Service, Service.id == ModelRoute.target_service_id)
            .where(ModelRoute.service_id == service.id)
            .where(ModelRoute.model_pattern != "*")
            .where(Service.is_active == True)
            .order_by(ModelRoute.priority)
        )

        models = []
        for route, target_svc in result.all():
            models.append({
                "id": route.model_pattern,
                "object": "model",
                "owned_by": target_svc.slug,
            })

        return JSONResponse(content={"object": "list", "data": models})


# Register the handler
registry.register("unified_llm", UnifiedLLMHandler())
