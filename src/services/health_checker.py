import time
import httpx
from src.models.service import Service

async def check_service_health(service: Service) -> dict:
    if not service.health_check_path:
        return {"status": "unknown", "detail": "No health check path configured"}

    url = service.base_url.rstrip("/") + "/" + service.health_check_path.lstrip("/")
    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.request(service.health_check_method, url)
            elapsed = (time.monotonic() - start) * 1000

            if resp.status_code < 400:
                return {"status": "ok", "detail": f"HTTP {resp.status_code}", "response_time_ms": round(elapsed, 1)}
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
