import time

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.service import Service


async def check_service_health(service: Service, session: AsyncSession | None = None) -> dict:
    # For unified_llm: check all target services
    if service.service_type == "unified_llm":
        return await _check_unified_health(service, session)

    if not service.health_check_path:
        return {"status": "unknown", "detail": "No health check path configured"}

    url = service.base_url.rstrip("/") + "/" + service.health_check_path.lstrip("/")
    start = time.monotonic()

    # Build auth headers based on service config
    headers: dict[str, str] = {}
    if service.auth_type == "bearer" and service.auth_token:
        headers["Authorization"] = f"Bearer {service.auth_token}"
    elif service.auth_type == "header" and service.auth_token:
        header_name = service.auth_header_name or "Authorization"
        headers[header_name] = service.auth_token
    if service.extra_headers:
        headers.update(service.extra_headers)

    # Query param auth
    if service.auth_type == "query_param" and service.auth_token:
        sep = "&" if "?" in url else "?"
        url += f"{sep}api_key={service.auth_token}"

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.request(service.health_check_method, url, headers=headers)
            elapsed = (time.monotonic() - start) * 1000

            if resp.status_code == 200:
                return {"status": "ok", "detail": f"HTTP {resp.status_code}", "response_time_ms": round(elapsed, 1)}
            elif resp.status_code < 400 or resp.status_code in (405, 422):
                return {"status": "warning", "detail": f"HTTP {resp.status_code}", "response_time_ms": round(elapsed, 1)}
            else:
                return {"status": "error", "detail": f"HTTP {resp.status_code}", "response_time_ms": round(elapsed, 1)}
    except httpx.ConnectError:
        elapsed = (time.monotonic() - start) * 1000
        return {"status": "error", "detail": "Connection refused", "response_time_ms": round(elapsed, 1)}
    except httpx.TimeoutException:
        elapsed = (time.monotonic() - start) * 1000
        return {"status": "error", "detail": "Timeout", "response_time_ms": round(elapsed, 1)}
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return {"status": "error", "detail": str(e), "response_time_ms": round(elapsed, 1)}


async def _check_unified_health(service: Service, session: AsyncSession | None) -> dict:
    """Check health of all target services in a unified_llm service."""
    if session is None:
        return {"status": "unknown", "detail": "Cannot check unified service without DB session"}

    from src.models.model_route import ModelRoute

    result = await session.execute(
        select(ModelRoute.target_service_id)
        .where(ModelRoute.service_id == service.id)
        .distinct()
    )
    target_ids = list(result.scalars().all())
    if not target_ids:
        return {"status": "warning", "detail": "No model routes configured"}

    start = time.monotonic()
    results = []
    for tid in target_ids:
        target = await session.get(Service, tid)
        if not target or not target.is_active:
            continue
        r = await check_service_health(target)
        results.append((target.slug, r))

    elapsed = (time.monotonic() - start) * 1000

    if not results:
        return {"status": "warning", "detail": "No active target services", "response_time_ms": round(elapsed, 1)}

    errors = [f"{slug}: {r['detail']}" for slug, r in results if r["status"] == "error"]
    if errors:
        return {"status": "error", "detail": f"{len(errors)}/{len(results)} targets down: {'; '.join(errors)}", "response_time_ms": round(elapsed, 1)}

    warnings = [slug for slug, r in results if r["status"] == "warning"]
    if warnings:
        return {"status": "warning", "detail": f"All {len(results)} targets reachable, {len(warnings)} with warnings", "response_time_ms": round(elapsed, 1)}

    return {"status": "ok", "detail": f"All {len(results)} targets healthy", "response_time_ms": round(elapsed, 1)}
