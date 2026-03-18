import time
import httpx
from src.models.service import Service


async def check_service_health(service: Service) -> dict:
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
