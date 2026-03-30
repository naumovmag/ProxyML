import httpx

_client: httpx.AsyncClient | None = None


def build_service_timeout(timeout_seconds: int) -> httpx.Timeout:
    """Build httpx.Timeout for a service. 0 means no timeout (wait indefinitely)."""
    read_timeout = None if timeout_seconds == 0 else float(timeout_seconds)
    return httpx.Timeout(read_timeout, connect=10.0)


async def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(None, connect=10.0),
            follow_redirects=True,
            verify=False,
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
        )
    return _client

async def close_http_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
