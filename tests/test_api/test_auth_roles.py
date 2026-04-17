import uuid

import pytest
from httpx import AsyncClient


async def _create_auth_system(client: AsyncClient, headers: dict, slug: str | None = None) -> dict:
    slug = slug or f"test-sys-{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/admin/auth-systems",
        json={"name": f"Test {slug}", "slug": slug, "users_active_by_default": True},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_permission_crud(client: AsyncClient, admin_headers: dict):
    system = await _create_auth_system(client, admin_headers)
    sid = system["id"]

    # Create
    resp = await client.post(
        f"/api/admin/auth-systems/{sid}/permissions",
        json={"slug": "posts.create", "name": "Create posts", "description": "allow creating posts"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    perm = resp.json()
    assert perm["slug"] == "posts.create"

    # List
    resp = await client.get(f"/api/admin/auth-systems/{sid}/permissions", headers=admin_headers)
    assert resp.status_code == 200
    assert any(p["id"] == perm["id"] for p in resp.json())

    # Update
    resp = await client.put(
        f"/api/admin/auth-systems/{sid}/permissions/{perm['id']}",
        json={"name": "Create new posts"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Create new posts"

    # Duplicate slug → 409
    resp = await client.post(
        f"/api/admin/auth-systems/{sid}/permissions",
        json={"slug": "posts.create", "name": "Another"},
        headers=admin_headers,
    )
    assert resp.status_code == 409

    # Delete
    resp = await client.delete(
        f"/api/admin/auth-systems/{sid}/permissions/{perm['id']}", headers=admin_headers
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_role_crud_and_assign_permissions(client: AsyncClient, admin_headers: dict):
    system = await _create_auth_system(client, admin_headers)
    sid = system["id"]

    # Create two permissions
    p1 = (await client.post(
        f"/api/admin/auth-systems/{sid}/permissions",
        json={"slug": "a.read", "name": "Read A"},
        headers=admin_headers,
    )).json()
    p2 = (await client.post(
        f"/api/admin/auth-systems/{sid}/permissions",
        json={"slug": "b.write", "name": "Write B"},
        headers=admin_headers,
    )).json()

    # Create role with one permission
    resp = await client.post(
        f"/api/admin/auth-systems/{sid}/roles",
        json={
            "slug": "editor",
            "name": "Editor",
            "description": "Editors",
            "is_default": True,
            "permission_ids": [p1["id"]],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    role = resp.json()
    assert role["is_default"] is True
    assert len(role["permissions"]) == 1
    assert role["permissions"][0]["slug"] == "a.read"

    # Set permissions (full replace)
    resp = await client.put(
        f"/api/admin/auth-systems/{sid}/roles/{role['id']}/permissions",
        json={"permission_ids": [p1["id"], p2["id"]]},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert {p["slug"] for p in resp.json()["permissions"]} == {"a.read", "b.write"}

    # Creating second default role unsets first
    resp2 = await client.post(
        f"/api/admin/auth-systems/{sid}/roles",
        json={"slug": "viewer", "name": "Viewer", "is_default": True, "permission_ids": []},
        headers=admin_headers,
    )
    assert resp2.status_code == 201
    # Re-fetch first role, its is_default must be False now
    resp = await client.get(f"/api/admin/auth-systems/{sid}/roles/{role['id']}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["is_default"] is False


@pytest.mark.asyncio
async def test_role_scope_isolation(client: AsyncClient, admin_headers: dict):
    """Permission from one system cannot be attached to a role in another system."""
    sys1 = await _create_auth_system(client, admin_headers)
    sys2 = await _create_auth_system(client, admin_headers)

    p_in_sys1 = (await client.post(
        f"/api/admin/auth-systems/{sys1['id']}/permissions",
        json={"slug": "foreign.perm", "name": "Foreign"},
        headers=admin_headers,
    )).json()

    # Attempt to create role in sys2 with a permission from sys1 → 400
    resp = await client.post(
        f"/api/admin/auth-systems/{sys2['id']}/roles",
        json={"slug": "x", "name": "x", "permission_ids": [p_in_sys1["id"]]},
        headers=admin_headers,
    )
    assert resp.status_code in (400, 404), resp.text


@pytest.mark.asyncio
async def test_user_roles_assignment_flow(client: AsyncClient, admin_headers: dict):
    system = await _create_auth_system(client, admin_headers)
    sid = system["id"]
    slug = system["slug"]

    # Create permission and role
    perm = (await client.post(
        f"/api/admin/auth-systems/{sid}/permissions",
        json={"slug": "dashboard.view", "name": "View dashboard"},
        headers=admin_headers,
    )).json()
    role = (await client.post(
        f"/api/admin/auth-systems/{sid}/roles",
        json={"slug": "member", "name": "Member", "permission_ids": [perm["id"]]},
        headers=admin_headers,
    )).json()

    # Register an end-user via public API
    email = f"u-{uuid.uuid4().hex[:8]}@test.local"
    resp = await client.post(
        f"/api/auth/{slug}/register",
        json={"email": email, "password": "password123", "fields": {}},
    )
    assert resp.status_code == 200, resp.text

    # Get user id via admin listing
    users_resp = await client.get(f"/api/admin/auth-systems/{sid}/users", headers=admin_headers)
    assert users_resp.status_code == 200
    users = users_resp.json()
    user = next(u for u in users if u["email"] == email)
    user_id = user["id"]
    assert user["roles"] == []  # no default role configured

    # Assign role
    resp = await client.put(
        f"/api/admin/auth-systems/{sid}/users/{user_id}/roles",
        json={"role_ids": [role["id"]]},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert any(r["id"] == role["id"] for r in resp.json())

    # Verify via listing
    users_resp = await client.get(f"/api/admin/auth-systems/{sid}/users", headers=admin_headers)
    user_after = next(u for u in users_resp.json() if u["id"] == user_id)
    assert any(r["slug"] == "member" for r in user_after["roles"])

    # Login → tokens; /me returns roles+permissions
    login = (await client.post(
        f"/api/auth/{slug}/login",
        json={"email": email, "password": "password123"},
    )).json()
    me = await client.get(
        f"/api/auth/{slug}/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert me.status_code == 200, me.text
    body = me.json()
    assert any(r["slug"] == "member" for r in body.get("roles", []))
    assert "dashboard.view" in body.get("permissions", [])

    # Remove role by DELETE
    resp = await client.delete(
        f"/api/admin/auth-systems/{sid}/users/{user_id}/roles/{role['id']}",
        headers=admin_headers,
    )
    assert resp.status_code == 204

    users_resp = await client.get(f"/api/admin/auth-systems/{sid}/users", headers=admin_headers)
    user_after = next(u for u in users_resp.json() if u["id"] == user_id)
    assert user_after["roles"] == []


@pytest.mark.asyncio
async def test_default_role_applied_on_registration(client: AsyncClient, admin_headers: dict):
    system = await _create_auth_system(client, admin_headers)
    sid = system["id"]
    slug = system["slug"]

    # Create a default role with a permission
    perm = (await client.post(
        f"/api/admin/auth-systems/{sid}/permissions",
        json={"slug": "basic.access", "name": "Basic"},
        headers=admin_headers,
    )).json()
    role = (await client.post(
        f"/api/admin/auth-systems/{sid}/roles",
        json={
            "slug": "user",
            "name": "User",
            "is_default": True,
            "permission_ids": [perm["id"]],
        },
        headers=admin_headers,
    )).json()

    email = f"u-{uuid.uuid4().hex[:8]}@test.local"
    reg = await client.post(
        f"/api/auth/{slug}/register",
        json={"email": email, "password": "password123", "fields": {}},
    )
    assert reg.status_code == 200

    # /me should show default role+permissions
    me = await client.get(
        f"/api/auth/{slug}/me",
        headers={"Authorization": f"Bearer {reg.json()['access_token']}"},
    )
    assert me.status_code == 200
    body = me.json()
    assert any(r["slug"] == "user" for r in body["roles"]), body
    assert "basic.access" in body["permissions"]
    # Cleanup: remove to keep role unique
    _ = role


@pytest.mark.asyncio
async def test_cannot_access_other_admin_auth_system_roles(
    client: AsyncClient, admin_headers: dict
):
    """Create system as admin A, register admin B, try to access A's roles → 404."""
    system = await _create_auth_system(client, admin_headers)
    sid = system["id"]

    # Register second admin (non-superadmin, pending)
    username = f"other-{uuid.uuid4().hex[:8]}"
    reg = await client.post(
        "/api/admin/register",
        json={"username": username, "password": "password123"},
    )
    # Registration itself needs no auth; admin is not approved
    assert reg.status_code in (200, 201)
    # Approve + promote via superadmin admin_headers
    # Fetch new admin id
    from src.db.session import get_async_session
    from src.models.admin_user import AdminUser
    from sqlalchemy import select
    from tests.conftest import test_session_factory

    async with test_session_factory() as s:
        u = (await s.execute(select(AdminUser).where(AdminUser.username == username))).scalar_one()
        u.is_approved = True
        await s.commit()

    login = await client.post(
        "/api/admin/login", json={"username": username, "password": "password123"}
    )
    assert login.status_code == 200, login.text
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Admin B tries to list A's roles → 404
    resp = await client.get(f"/api/admin/auth-systems/{sid}/roles", headers=other_headers)
    assert resp.status_code == 404

    # And cannot create permissions/roles in A's system
    resp = await client.post(
        f"/api/admin/auth-systems/{sid}/permissions",
        json={"slug": "hack", "name": "Hack"},
        headers=other_headers,
    )
    assert resp.status_code == 404
