import logging
from fastapi import Request
from fastapi.responses import StreamingResponse, Response
from src.models.service import Service
from src.proxy.base import AbstractProxyHandler, registry
from src.proxy.client import get_http_client
from src.proxy.auth import get_auth_strategy
from src.proxy.streaming import stream_response

logger = logging.getLogger(__name__)

class GenericProxyHandler(AbstractProxyHandler):
    async def handle(self, request: Request, service: Service, path: str) -> Response:
        client = await get_http_client()

        # Build target URL
        target_url = f"{service.base_url.rstrip('/')}/{path.lstrip('/')}"
        if request.url.query:
            target_url += f"?{request.url.query}"

        # Read request body
        body = await request.body()

        # Build headers - forward relevant ones
        headers = {}
        for key, value in request.headers.items():
            lower = key.lower()
            if lower in ("host", "x-api-key", "connection", "transfer-encoding"):
                continue
            headers[key] = value

        # Apply extra headers from service config
        if service.extra_headers:
            headers.update(service.extra_headers)

        # Apply backend auth
        auth_strategy = get_auth_strategy(service.auth_type)

        # Check if streaming is requested
        is_streaming = service.supports_streaming
        if body:
            try:
                import json
                body_json = json.loads(body)
                if body_json.get("stream"):
                    is_streaming = True
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        # Apply auth to headers directly
        if service.auth_type == "bearer":
            headers["Authorization"] = f"Bearer {service.auth_token}"
        elif service.auth_type == "header":
            header_name = service.auth_header_name or "Authorization"
            headers[header_name] = service.auth_token or ""
        elif service.auth_type == "query_param":
            sep = "&" if "?" in target_url else "?"
            target_url += f"{sep}api_key={service.auth_token or ''}"

        import httpx
        timeout = httpx.Timeout(float(service.timeout_seconds), connect=10.0)

        if is_streaming:
            # Streaming response
            req = client.build_request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body if body else None,
                timeout=timeout,
            )
            response = await client.send(req, stream=True)

            response_headers = dict(response.headers)
            # Remove hop-by-hop headers
            for h in ("transfer-encoding", "connection", "content-length"):
                response_headers.pop(h, None)

            return StreamingResponse(
                stream_response(response),
                status_code=response.status_code,
                headers=response_headers,
                media_type=response.headers.get("content-type", "text/event-stream"),
            )
        else:
            # Non-streaming response
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body if body else None,
                timeout=timeout,
            )

            response_headers = dict(response.headers)
            for h in ("transfer-encoding", "connection", "content-encoding"):
                response_headers.pop(h, None)

            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers,
                media_type=response.headers.get("content-type"),
            )

# Register the default handler
registry.set_default(GenericProxyHandler())
