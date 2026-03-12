import httpx
from typing import AsyncGenerator

async def stream_response(response: httpx.Response) -> AsyncGenerator[bytes, None]:
    async for chunk in response.aiter_bytes(1024):
        yield chunk

async def stream_sse(response: httpx.Response) -> AsyncGenerator[bytes, None]:
    async for line in response.aiter_lines():
        yield f"{line}\n".encode("utf-8")
    yield b"\n"
