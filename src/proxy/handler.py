import json
import time
import logging
import httpx
from fastapi import Request
from fastapi.responses import StreamingResponse, Response
from src.models.service import Service
from src.models.api_key import ApiKey
from src.proxy.base import AbstractProxyHandler, registry
from src.proxy.client import get_http_client
from src.proxy.streaming import stream_response
from src.services.request_logger import log_request_fire_and_forget
from src.cache.proxy_cache import get_cached_response, set_cached_response

logger = logging.getLogger(__name__)


class GenericProxyHandler(AbstractProxyHandler):
    async def handle(
        self,
        request: Request,
        service: Service,
        path: str,
        api_key: ApiKey | None = None,
    ) -> Response:
        client = await get_http_client()
        start = time.monotonic()

        # Build target URL
        target_url = f"{service.base_url.rstrip('/')}/{path.lstrip('/')}"
        if request.url.query:
            target_url += f"?{request.url.query}"

        # Read request body
        body = await request.body()
        request_size = len(body)
        query_string = str(request.url.query) if request.url.query else ""

        # Check cache (only for non-streaming)
        use_cache = getattr(service, 'cache_enabled', False)
        if use_cache:
            cached = await get_cached_response(
                service.slug, request.method, path, query_string, body,
            )
            if cached:
                duration_ms = (time.monotonic() - start) * 1000
                content_bytes = bytes.fromhex(cached["content"])
                log_request_fire_and_forget(
                    service_id=service.id,
                    service_slug=service.slug,
                    api_key_id=api_key.id if api_key else None,
                    api_key_name=api_key.name if api_key else None,
                    method=request.method,
                    path=path,
                    status_code=cached["status_code"],
                    request_size=request_size,
                    response_size=len(content_bytes),
                    duration_ms=round(duration_ms, 1),
                    is_streaming=False,
                    is_cached=True,
                )
                resp_headers = cached["headers"]
                resp_headers["X-ProxyML-Cache"] = "HIT"
                return Response(
                    content=content_bytes,
                    status_code=cached["status_code"],
                    headers=resp_headers,
                    media_type=resp_headers.get("content-type"),
                )

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

        # Streaming only when explicitly requested in body
        is_streaming = False
        if service.supports_streaming and body:
            try:
                body_json = json.loads(body)
                if body_json.get("stream") is True:
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

        timeout = httpx.Timeout(float(service.timeout_seconds), connect=10.0)

        try:
            if is_streaming:
                req = client.build_request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=body if body else None,
                    timeout=timeout,
                )
                response = await client.send(req, stream=True)

                response_headers = dict(response.headers)
                for h in ("transfer-encoding", "connection", "content-length"):
                    response_headers.pop(h, None)

                # Wrap stream to count bytes and log on completion
                streamed_bytes = 0

                async def logging_stream():
                    nonlocal streamed_bytes
                    try:
                        async for chunk in stream_response(response):
                            streamed_bytes += len(chunk)
                            yield chunk
                    finally:
                        duration_ms = (time.monotonic() - start) * 1000
                        log_request_fire_and_forget(
                            service_id=service.id,
                            service_slug=service.slug,
                            api_key_id=api_key.id if api_key else None,
                            api_key_name=api_key.name if api_key else None,
                            method=request.method,
                            path=path,
                            status_code=response.status_code,
                            request_size=request_size,
                            response_size=streamed_bytes,
                            duration_ms=round(duration_ms, 1),
                            is_streaming=True,
                        )

                return StreamingResponse(
                    logging_stream(),
                    status_code=response.status_code,
                    headers=response_headers,
                    media_type=response.headers.get("content-type", "text/event-stream"),
                )
            else:
                response = await client.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=body if body else None,
                    timeout=timeout,
                )

                duration_ms = (time.monotonic() - start) * 1000
                log_request_fire_and_forget(
                    service_id=service.id,
                    service_slug=service.slug,
                    api_key_id=api_key.id if api_key else None,
                    api_key_name=api_key.name if api_key else None,
                    method=request.method,
                    path=path,
                    status_code=response.status_code,
                    request_size=request_size,
                    response_size=len(response.content),
                    duration_ms=round(duration_ms, 1),
                    is_streaming=False,
                )

                response_headers = dict(response.headers)
                for h in ("transfer-encoding", "connection", "content-encoding"):
                    response_headers.pop(h, None)

                # Cache successful responses
                if use_cache and response.status_code < 400:
                    await set_cached_response(
                        service.slug, request.method, path, query_string, body,
                        response.status_code, response_headers, response.content,
                        ttl=getattr(service, 'cache_ttl_seconds', 86400),
                    )
                    response_headers["X-ProxyML-Cache"] = "MISS"

                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=response_headers,
                    media_type=response.headers.get("content-type"),
                )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            log_request_fire_and_forget(
                service_id=service.id,
                service_slug=service.slug,
                api_key_id=api_key.id if api_key else None,
                api_key_name=api_key.name if api_key else None,
                method=request.method,
                path=path,
                status_code=502,
                request_size=request_size,
                response_size=0,
                duration_ms=round(duration_ms, 1),
                is_streaming=is_streaming,
                error=str(e),
            )
            raise


# Register the default handler
registry.set_default(GenericProxyHandler())
