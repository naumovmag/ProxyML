import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_service(client: AsyncClient, admin_headers: dict):
    # Create
    service_data = {
        "name": "Test Service",
        "slug": "test-svc",
        "service_type": "custom",
        "base_url": "http://example.com",
        "auth_type": "none",
    }
    resp = await client.post("/api/admin/services", json=service_data, headers=admin_headers)
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "Test Service"
    assert created["slug"] == "test-svc"
    service_id = created["id"]

    # List
    resp = await client.get("/api/admin/services", headers=admin_headers)
    assert resp.status_code == 200
    services = resp.json()
    assert any(s["id"] == service_id for s in services)

    # Public catalog
    resp = await client.get("/api/v1/services")
    assert resp.status_code == 200
    catalog = resp.json()
    assert any(s["slug"] == "test-svc" for s in catalog)

    # Update
    resp = await client.put(f"/api/admin/services/{service_id}", json={"description": "updated"}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["description"] == "updated"

    # Delete
    resp = await client.delete(f"/api/admin/services/{service_id}", headers=admin_headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_create_api_key(client: AsyncClient, admin_headers: dict):
    resp = await client.post("/api/admin/api-keys", json={"name": "Test Key"}, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "raw_key" in data
    assert data["raw_key"].startswith("pml_")
    assert data["name"] == "Test Key"
