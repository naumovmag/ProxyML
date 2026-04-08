import json
import logging
import time
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.load_test import LoadTestResult
from src.models.model_route import ModelRoute
from src.models.service import Service
from src.proxy.client import build_service_timeout, get_http_client
from src.services.load_test_payloads import get_default_payload

logger = logging.getLogger(__name__)


def _build_target(service, path: str) -> str:
    base = service.base_url.rstrip("/")
    if path:
        return f"{base}/{path.lstrip('/')}"
    return base


def _apply_auth(headers: dict, service) -> str | None:
    if service.auth_type == "bearer":
        headers["Authorization"] = f"Bearer {service.auth_token}"
    elif service.auth_type == "header":
        header_name = service.auth_header_name or "Authorization"
        headers[header_name] = service.auth_token or ""
    elif service.auth_type == "query_param":
        return f"api_key={service.auth_token or ''}"
    return None


async def _resolve_unified_target(session: AsyncSession, service, body: dict | None):
    """For unified_llm services, resolve target service from model in body."""
    if service.service_type != "unified_llm" or session is None:
        return service
    model_name = body.get("model") if isinstance(body, dict) else None
    result = await session.execute(
        select(ModelRoute)
        .where(ModelRoute.service_id == service.id)
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
                return target
    if default_route:
        target = await session.get(Service, default_route.target_service_id)
        if target and target.is_active:
            return target
    return service


async def execute_single_test(task, service, session: AsyncSession | None = None) -> LoadTestResult:
    path = task.test_path
    body = task.test_body
    if body is None:
        default = get_default_payload(task.service_type)
        body = default["body"]
        if not path:
            path = default["path"]

    # Inject model from service if not explicitly set in body
    if isinstance(body, dict) and "model" not in body and service.default_model:
        body = {**body, "model": service.default_model}

    # Add unique nonce to defeat caching (both proxy cache and LLM KV-cache)
    if isinstance(body, dict) and "messages" in body and isinstance(body["messages"], list):
        nonce = uuid.uuid4().hex[:8]
        body = {**body, "messages": [*body["messages"], {"role": "user", "content": f"[nonce:{nonce}]"}]}

    # For unified_llm: resolve actual target service
    actual_service = await _resolve_unified_target(session, service, body)

    target_url = _build_target(actual_service, path)

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if actual_service.extra_headers:
        headers.update(actual_service.extra_headers)
    if task.test_headers:
        headers.update(task.test_headers)

    query_suffix = _apply_auth(headers, actual_service)
    if query_suffix:
        sep = "&" if "?" in target_url else "?"
        target_url += f"{sep}{query_suffix}"

    content: bytes | None = None
    if body is not None:
        if isinstance(body, str):
            content = body.encode()
        else:
            content = json.dumps(body).encode()

    timeout = build_service_timeout(actual_service.timeout_seconds)
    client = await get_http_client()
    start = time.monotonic()

    try:
        response = await client.request(
            method=task.test_method or "POST",
            url=target_url,
            headers=headers,
            content=content,
            timeout=timeout,
        )
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        logger.info(f"Load test {task.id}: {response.status_code} {duration_ms}ms | body: {response.text[:500]}")

        return LoadTestResult(
            task_id=task.id,
            owner_id=task.owner_id,
            service_id=task.service_id,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_size=len(content) if content else 0,
            response_size=len(response.content),
            response_body=response.text[:2000],
            error=None,
        )
    except httpx.TimeoutException:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        return LoadTestResult(
            task_id=task.id,
            owner_id=task.owner_id,
            service_id=task.service_id,
            status_code=504,
            duration_ms=duration_ms,
            request_size=len(content) if content else 0,
            response_size=0,
            error="Timeout",
        )
    except httpx.ConnectError as e:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        return LoadTestResult(
            task_id=task.id,
            owner_id=task.owner_id,
            service_id=task.service_id,
            status_code=502,
            duration_ms=duration_ms,
            request_size=len(content) if content else 0,
            response_size=0,
            error=f"Connection failed: {e}",
        )
    except Exception as e:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        logger.error(f"Load test error for task {task.id}: {e}")
        return LoadTestResult(
            task_id=task.id,
            owner_id=task.owner_id,
            service_id=task.service_id,
            status_code=0,
            duration_ms=duration_ms,
            request_size=len(content) if content else 0,
            response_size=0,
            error=str(e),
        )
