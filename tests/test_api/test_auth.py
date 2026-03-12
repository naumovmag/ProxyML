import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    resp = await client.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_failure(client: AsyncClient):
    resp = await client.post("/api/admin/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_no_token(client: AsyncClient):
    resp = await client.get("/api/admin/services")
    assert resp.status_code in (401, 403)
