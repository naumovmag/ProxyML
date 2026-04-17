"""Integration tests for public auth-system admin endpoints.

Tests the /{slug}/users* and /{slug}/roles endpoints that require
an end-user with is_admin_role=True.
"""
import uuid

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_system(client: AsyncClient, headers: dict) -> dict:
    slug = f"pa-{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/admin/auth-systems",
        json={"name": f"Test {slug}", "slug": slug, "users_active_by_default": True},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_permission(client: AsyncClient, headers: dict, sid: str, slug: str) -> dict:
    resp = await client.post(
        f"/api/admin/auth-systems/{sid}/permissions",
        json={"slug": slug, "name": slug},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_role(
    client: AsyncClient,
    headers: dict,
    sid: str,
    slug: str,
    is_admin_role: bool = False,
    permission_ids: list | None = None,
) -> dict:
    resp = await client.post(
        f"/api/admin/auth-systems/{sid}/roles",
        json={
            "slug": slug,
            "name": slug,
            "is_admin_role": is_admin_role,
            "permission_ids": permission_ids or [],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _register_user(client: AsyncClient, slug: str) -> dict:
    email = f"u-{uuid.uuid4().hex[:8]}@test.local"
    resp = await client.post(
        f"/api/auth/{slug}/register",
        json={"email": email, "password": "password123", "fields": {}},
    )
    assert resp.status_code == 200, resp.text
    return {"token": resp.json()["access_token"], "email": email}


async def _assign_role(
    client: AsyncClient, headers: dict, sid: str, user_id: str, role_id: str
) -> None:
    resp = await client.put(
        f"/api/admin/auth-systems/{sid}/users/{user_id}/roles",
        json={"role_ids": [role_id]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


async def _get_user_id(client: AsyncClient, headers: dict, sid: str, email: str) -> str:
    resp = await client.get(f"/api/admin/auth-systems/{sid}/users", headers=headers)
    assert resp.status_code == 200
    users = resp.json()
    user = next(u for u in users if u["email"] == email)
    return user["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_admin_user_cannot_list_users(client: AsyncClient, admin_headers: dict):
    """User without admin role gets 403 on GET /users."""
    system = await _create_system(client, admin_headers)
    sid = system["id"]
    slug = system["slug"]

    user_a = await _register_user(client, slug)

    resp = await client.get(
        f"/api/auth/{slug}/users",
        headers={"Authorization": f"Bearer {user_a['token']}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_user_can_list_users(client: AsyncClient, admin_headers: dict):
    """After assigning admin role, user A can list users."""
    system = await _create_system(client, admin_headers)
    sid = system["id"]
    slug = system["slug"]

    # Create admin role with is_admin_role=True
    perm = await _create_permission(client, admin_headers, sid, "x.read")
    admin_role = await _create_role(
        client, admin_headers, sid, "admin", is_admin_role=True, permission_ids=[perm["id"]]
    )
    member_role = await _create_role(client, admin_headers, sid, "member")

    # Register user A
    user_a = await _register_user(client, slug)
    user_a_id = await _get_user_id(client, admin_headers, sid, user_a["email"])

    # Before role assignment: 403
    resp = await client.get(
        f"/api/auth/{slug}/users",
        headers={"Authorization": f"Bearer {user_a['token']}"},
    )
    assert resp.status_code == 403

    # Assign admin role via ProxyML admin API
    await _assign_role(client, admin_headers, sid, user_a_id, admin_role["id"])

    # Need fresh token after role assignment — login again
    login = await client.post(
        f"/api/auth/{slug}/login",
        json={"email": user_a["email"], "password": "password123"},
    )
    assert login.status_code == 200
    admin_token = login.json()["access_token"]

    # Now listing users works
    resp = await client.get(
        f"/api/auth/{slug}/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    users = resp.json()
    assert any(u["email"] == user_a["email"] for u in users)
    # Verify roles field is present
    user_entry = next(u for u in users if u["email"] == user_a["email"])
    assert any(r["slug"] == "admin" for r in user_entry["roles"])


@pytest.mark.asyncio
async def test_admin_can_change_other_user_roles(client: AsyncClient, admin_headers: dict):
    """User A (admin) can assign/replace roles of user B."""
    system = await _create_system(client, admin_headers)
    sid = system["id"]
    slug = system["slug"]

    admin_role = await _create_role(client, admin_headers, sid, "admin", is_admin_role=True)
    member_role = await _create_role(client, admin_headers, sid, "member")

    user_a = await _register_user(client, slug)
    user_b = await _register_user(client, slug)

    user_a_id = await _get_user_id(client, admin_headers, sid, user_a["email"])
    user_b_id = await _get_user_id(client, admin_headers, sid, user_b["email"])

    # Assign admin role to A via admin API
    await _assign_role(client, admin_headers, sid, user_a_id, admin_role["id"])

    login_a = await client.post(
        f"/api/auth/{slug}/login",
        json={"email": user_a["email"], "password": "password123"},
    )
    admin_token = login_a.json()["access_token"]
    auth_hdr = {"Authorization": f"Bearer {admin_token}"}

    # A sets member role for B
    resp = await client.put(
        f"/api/auth/{slug}/users/{user_b_id}/roles",
        json={"role_ids": [member_role["id"]]},
        headers=auth_hdr,
    )
    assert resp.status_code == 200, resp.text
    role_slugs = [r["slug"] for r in resp.json()]
    assert "member" in role_slugs

    # GET /users/{user_b_id}/roles
    resp2 = await client.get(
        f"/api/auth/{slug}/users/{user_b_id}/roles",
        headers=auth_hdr,
    )
    assert resp2.status_code == 200
    assert any(r["slug"] == "member" for r in resp2.json())


@pytest.mark.asyncio
async def test_admin_cannot_remove_own_last_admin_role(client: AsyncClient, admin_headers: dict):
    """Admin cannot remove their own last admin role via PUT /users/{id}/roles."""
    system = await _create_system(client, admin_headers)
    sid = system["id"]
    slug = system["slug"]

    admin_role = await _create_role(client, admin_headers, sid, "admin", is_admin_role=True)
    member_role = await _create_role(client, admin_headers, sid, "member")

    user_a = await _register_user(client, slug)
    user_a_id = await _get_user_id(client, admin_headers, sid, user_a["email"])

    # Assign both roles to A
    resp = await client.put(
        f"/api/admin/auth-systems/{sid}/users/{user_a_id}/roles",
        json={"role_ids": [admin_role["id"], member_role["id"]]},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    login_a = await client.post(
        f"/api/auth/{slug}/login",
        json={"email": user_a["email"], "password": "password123"},
    )
    admin_token = login_a.json()["access_token"]
    auth_hdr = {"Authorization": f"Bearer {admin_token}"}

    # Try to replace A's roles with only member_role (removing last admin role)
    resp = await client.put(
        f"/api/auth/{slug}/users/{user_a_id}/roles",
        json={"role_ids": [member_role["id"]]},
        headers=auth_hdr,
    )
    assert resp.status_code == 400
    assert "admin" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_cannot_delete_own_last_admin_role(client: AsyncClient, admin_headers: dict):
    """Admin cannot DELETE their own last admin role."""
    system = await _create_system(client, admin_headers)
    sid = system["id"]
    slug = system["slug"]

    admin_role = await _create_role(client, admin_headers, sid, "admin", is_admin_role=True)

    user_a = await _register_user(client, slug)
    user_a_id = await _get_user_id(client, admin_headers, sid, user_a["email"])
    await _assign_role(client, admin_headers, sid, user_a_id, admin_role["id"])

    login_a = await client.post(
        f"/api/auth/{slug}/login",
        json={"email": user_a["email"], "password": "password123"},
    )
    admin_token = login_a.json()["access_token"]
    auth_hdr = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.delete(
        f"/api/auth/{slug}/users/{user_a_id}/roles/{admin_role['id']}",
        headers=auth_hdr,
    )
    assert resp.status_code == 400
    assert "admin" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_cannot_access_user_from_other_system(client: AsyncClient, admin_headers: dict):
    """Admin in system A gets 404 when accessing a user from system B."""
    sys_a = await _create_system(client, admin_headers)
    sys_b = await _create_system(client, admin_headers)

    admin_role = await _create_role(client, admin_headers, sys_a["id"], "admin", is_admin_role=True)

    user_a = await _register_user(client, sys_a["slug"])
    user_b = await _register_user(client, sys_b["slug"])

    user_a_id = await _get_user_id(client, admin_headers, sys_a["id"], user_a["email"])
    user_b_id = await _get_user_id(client, admin_headers, sys_b["id"], user_b["email"])

    await _assign_role(client, admin_headers, sys_a["id"], user_a_id, admin_role["id"])

    login_a = await client.post(
        f"/api/auth/{sys_a['slug']}/login",
        json={"email": user_a["email"], "password": "password123"},
    )
    admin_token = login_a.json()["access_token"]
    auth_hdr = {"Authorization": f"Bearer {admin_token}"}

    # A tries to get user B who belongs to system B → 404
    resp = await client.get(
        f"/api/auth/{sys_a['slug']}/users/{user_b_id}",
        headers=auth_hdr,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_list_roles(client: AsyncClient, admin_headers: dict):
    """Admin user can list all roles in their auth system."""
    system = await _create_system(client, admin_headers)
    sid = system["id"]
    slug = system["slug"]

    admin_role = await _create_role(client, admin_headers, sid, "admin", is_admin_role=True)
    _ = await _create_role(client, admin_headers, sid, "viewer")

    user_a = await _register_user(client, slug)
    user_a_id = await _get_user_id(client, admin_headers, sid, user_a["email"])
    await _assign_role(client, admin_headers, sid, user_a_id, admin_role["id"])

    login_a = await client.post(
        f"/api/auth/{slug}/login",
        json={"email": user_a["email"], "password": "password123"},
    )
    admin_token = login_a.json()["access_token"]

    resp = await client.get(
        f"/api/auth/{slug}/roles",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    slugs = [r["slug"] for r in resp.json()]
    assert "admin" in slugs
    assert "viewer" in slugs
    # Verify is_admin_role flag is present
    admin_entry = next(r for r in resp.json() if r["slug"] == "admin")
    assert admin_entry["is_admin_role"] is True
