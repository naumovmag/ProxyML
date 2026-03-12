import time
import logging
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("proxyml.access")


class LoggingMiddleware:
    """Pure ASGI middleware — does not buffer responses, safe for SSE streaming."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = (time.monotonic() - start) * 1000
            method = scope.get("method", "?")
            path = scope.get("path", "?")
            logger.info(f"{method} {path} -> {status_code} ({elapsed:.0f}ms)")
