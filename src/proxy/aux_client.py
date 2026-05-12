import httpx

_aux_client: httpx.AsyncClient | None = None


async def get_aux_http_client() -> httpx.AsyncClient:
    """Shared client for auxiliary calls: health checks, AI, SMS, email providers."""
    global _aux_client
    if _aux_client is None or _aux_client.is_closed:
        _aux_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            verify=False,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
    return _aux_client


async def close_aux_http_client():
    global _aux_client
    if _aux_client and not _aux_client.is_closed:
        await _aux_client.aclose()
        _aux_client = None
