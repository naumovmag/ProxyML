import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("proxyml.access")

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        elapsed = (time.monotonic() - start) * 1000
        logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({elapsed:.0f}ms)")
        return response
