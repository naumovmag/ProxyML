import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_current_admin
from src.services.service_registry import (
    list_services, get_service_by_id, get_service_by_slug, create_service, update_service, delete_service,
    FallbackValidationError,
)
from src.services.service_access import check_service_access, list_accessible_services
from src.schemas.service import ServiceCreate, ServiceUpdate, ServiceRead, ServiceShareCreate, ServiceShareRead
from src.models.service_group import ServiceGroup
from src.models.service_share import ServiceShare
from src.models.admin_user import AdminUser

router = APIRouter()


def _service_to_read(item: dict) -> ServiceRead:
    """Convert list_accessible_services item dict to ServiceRead."""
    svc = item["service"]
    updates = {
        "role": item["role"],
        "owner_username": item["owner_username"],
        "owner_display_name": item["owner_display_name"],
        "shared_with_count": item["shared_with_count"],
    }
    # For shared services, use the share's group_id (recipient's grouping)
    if "override_group_id" in item:
        updates["group_id"] = item["override_group_id"]
    return ServiceRead.model_validate(svc, from_attributes=True).model_copy(update=updates)


@router.get("/services", response_model=list[ServiceRead])
async def admin_list_services(
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    items = await list_accessible_services(session, admin.id)
    return [_service_to_read(item) for item in items]


@router.get("/services/{service_id}", response_model=ServiceRead)
async def admin_get_service(
    service_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    svc, role = await check_service_access(session, service_id, admin.id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return svc


@router.post("/services", response_model=ServiceRead, status_code=201)
async def admin_create_service(
    data: ServiceCreate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        return await create_service(session, data, owner_id=admin.id)
    except FallbackValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/services/{service_id}", response_model=ServiceRead)
async def admin_update_service(
    service_id: uuid.UUID,
    data: ServiceUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    svc, role = await check_service_access(session, service_id, admin.id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    # Shared users can only change their own group_id (via share record)
    if role == "shared":
        if "group_id" in data.model_fields_set:
            share_result = await session.execute(
                select(ServiceShare).where(
                    ServiceShare.service_id == service_id,
                    ServiceShare.shared_with_user_id == admin.id,
                )
            )
            share = share_result.scalar_one_or_none()
            if share:
                share.group_id = data.group_id
                await session.commit()
            await session.refresh(svc)
            return svc
        raise HTTPException(status_code=403, detail="Only the owner can edit this service")
    try:
        svc = await update_service(session, service_id, data)
    except FallbackValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return svc


@router.delete("/services/{service_id}", status_code=204)
async def admin_delete_service(
    service_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    svc = await get_service_by_id(session, service_id)
    if not svc or svc.owner_id != admin.id:
        raise HTTPException(status_code=404, detail="Service not found")
    await delete_service(session, service_id)


# ─── Sharing endpoints ───


@router.post("/services/{service_id}/shares", response_model=ServiceShareRead, status_code=201)
async def share_service(
    service_id: uuid.UUID,
    data: ServiceShareCreate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    svc = await get_service_by_id(session, service_id)
    if not svc or svc.owner_id != admin.id:
        raise HTTPException(status_code=404, detail="Service not found")
    if data.user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot share a service with yourself")
    # Check target user exists and is active+approved
    target_result = await session.execute(select(AdminUser).where(AdminUser.id == data.user_id))
    target_user = target_result.scalar_one_or_none()
    if not target_user or not target_user.is_active or not target_user.is_approved:
        raise HTTPException(status_code=404, detail="Target user not found or inactive")
    # Check not already shared
    existing = await session.execute(
        select(ServiceShare).where(
            ServiceShare.service_id == service_id,
            ServiceShare.shared_with_user_id == data.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Service already shared with this user")
    share = ServiceShare(
        service_id=service_id,
        shared_with_user_id=data.user_id,
        shared_by_user_id=admin.id,
    )
    session.add(share)
    await session.commit()
    await session.refresh(share)
    # Fetch shared_by username
    return ServiceShareRead(
        id=share.id,
        service_id=share.service_id,
        shared_with_user_id=share.shared_with_user_id,
        shared_with_username=target_user.username,
        shared_with_display_name=target_user.display_name,
        shared_by_user_id=share.shared_by_user_id,
        shared_by_username=admin.username,
        created_at=share.created_at,
    )


@router.get("/services/{service_id}/shares", response_model=list[ServiceShareRead])
async def list_service_shares(
    service_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    svc = await get_service_by_id(session, service_id)
    if not svc or svc.owner_id != admin.id:
        raise HTTPException(status_code=404, detail="Service not found")
    result = await session.execute(
        select(ServiceShare, AdminUser)
        .join(AdminUser, AdminUser.id == ServiceShare.shared_with_user_id)
        .where(ServiceShare.service_id == service_id)
        .order_by(ServiceShare.created_at)
    )
    items = []
    for share, user in result.all():
        # Get shared_by username
        by_result = await session.execute(select(AdminUser.username).where(AdminUser.id == share.shared_by_user_id))
        by_username = by_result.scalar_one_or_none() or "unknown"
        items.append(ServiceShareRead(
            id=share.id,
            service_id=share.service_id,
            shared_with_user_id=share.shared_with_user_id,
            shared_with_username=user.username,
            shared_with_display_name=user.display_name,
            shared_by_user_id=share.shared_by_user_id,
            shared_by_username=by_username,
            created_at=share.created_at,
        ))
    return items


@router.delete("/services/{service_id}/shares/{user_id}", status_code=204)
async def revoke_share(
    service_id: uuid.UUID,
    user_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    svc = await get_service_by_id(session, service_id)
    if not svc or svc.owner_id != admin.id:
        raise HTTPException(status_code=404, detail="Service not found")
    result = await session.execute(
        sa_delete(ServiceShare).where(
            ServiceShare.service_id == service_id,
            ServiceShare.shared_with_user_id == user_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Share not found")
    await session.commit()


@router.delete("/services/{service_id}/unshare", status_code=204)
async def unshare_service(
    service_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        sa_delete(ServiceShare).where(
            ServiceShare.service_id == service_id,
            ServiceShare.shared_with_user_id == admin.id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Share not found")
    await session.commit()


@router.get("/services-export")
async def export_services(
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Export all groups and services with all fields including auth tokens as JSON."""
    groups_result = await session.execute(
        select(ServiceGroup)
        .where(ServiceGroup.owner_id == admin.id)
        .order_by(ServiceGroup.sort_order, ServiceGroup.name)
    )
    groups = list(groups_result.scalars().all())
    groups_map = {g.id: g.name for g in groups}

    groups_data = [
        {"name": g.name, "description": g.description, "sort_order": g.sort_order}
        for g in groups
    ]

    services = await list_services(session, owner_id=admin.id)
    id_to_slug = {s.id: s.slug for s in services}

    services_data = []
    for s in services:
        services_data.append({
            "name": s.name,
            "slug": s.slug,
            "group_name": groups_map.get(s.group_id) if s.group_id else None,
            "service_type": s.service_type,
            "base_url": s.base_url,
            "auth_type": s.auth_type,
            "auth_token": s.auth_token,
            "auth_header_name": s.auth_header_name,
            "default_model": s.default_model,
            "timeout_seconds": s.timeout_seconds,
            "supports_streaming": s.supports_streaming,
            "extra_headers": s.extra_headers,
            "health_check_path": s.health_check_path,
            "health_check_method": s.health_check_method,
            "description": s.description,
            "tags": s.tags,
            "request_schema_hint": s.request_schema_hint,
            "cache_enabled": s.cache_enabled,
            "cache_ttl_seconds": s.cache_ttl_seconds,
            "fallback_service_slug": id_to_slug.get(s.fallback_service_id) if s.fallback_service_id else None,
            "fallback_on_statuses": s.fallback_on_statuses,
            "is_active": s.is_active,
        })
    return JSONResponse(
        content={"version": 2, "groups": groups_data, "services": services_data},
        headers={"Content-Disposition": "attachment; filename=proxyml-services-export.json"},
    )


@router.post("/services-import")
async def import_services(
    file: UploadFile = File(...),
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Import groups and services from JSON file. Matches by name/slug, updates existing."""
    import json

    content = await file.read()
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object with 'services' and optional 'groups'")

    # --- Import groups first ---
    groups_data = data.get("groups", [])
    group_name_to_id: dict[str, uuid.UUID] = {}
    groups_created = 0
    groups_updated = 0

    if isinstance(groups_data, list):
        for g_item in groups_data:
            name = g_item.get("name")
            if not name:
                continue
            result = await session.execute(
                select(ServiceGroup).where(ServiceGroup.name == name, ServiceGroup.owner_id == admin.id)
            )
            existing_group = result.scalar_one_or_none()
            if existing_group:
                if "description" in g_item:
                    existing_group.description = g_item["description"]
                if "sort_order" in g_item:
                    existing_group.sort_order = g_item["sort_order"]
                group_name_to_id[name] = existing_group.id
                groups_updated += 1
            else:
                new_group = ServiceGroup(
                    name=name,
                    description=g_item.get("description"),
                    sort_order=g_item.get("sort_order", 0),
                    owner_id=admin.id,
                )
                session.add(new_group)
                await session.flush()
                group_name_to_id[name] = new_group.id
                groups_created += 1
        await session.commit()

    # Load all existing groups for this owner
    all_groups = await session.execute(
        select(ServiceGroup).where(ServiceGroup.owner_id == admin.id)
    )
    for g in all_groups.scalars().all():
        group_name_to_id[g.name] = g.id

    # --- Import services ---
    services_data = data.get("services", data) if "services" in data else data
    if not isinstance(services_data, list):
        raise HTTPException(status_code=400, detail="Expected 'services' to be a list")

    created = 0
    updated = 0
    errors = []
    skip_keys = {"id", "created_at", "updated_at", "group_id", "group_name", "fallback_service_slug", "owner_id"}
    fallback_links: list[tuple[str, str]] = []

    for i, item in enumerate(services_data):
        try:
            slug = item.get("slug")
            if not slug:
                errors.append(f"Item {i}: missing slug")
                continue

            group_id = None
            group_name = item.get("group_name")
            if group_name and group_name in group_name_to_id:
                group_id = group_name_to_id[group_name]

            svc_fields = {k: v for k, v in item.items() if k not in skip_keys}
            svc_fields["group_id"] = group_id
            svc_fields.pop("fallback_service_id", None)

            existing = await get_service_by_slug(session, slug)
            if existing:
                if existing.owner_id != admin.id:
                    errors.append(f"Item {i} (slug={slug}): slug already used by another user")
                    continue
                update_data = ServiceUpdate(**svc_fields)
                await update_service(session, existing.id, update_data)
                updated += 1
            else:
                svc_data = ServiceCreate(**svc_fields)
                await create_service(session, svc_data, owner_id=admin.id)
                created += 1

            fallback_slug = item.get("fallback_service_slug")
            if fallback_slug:
                fallback_links.append((slug, fallback_slug))
        except Exception as e:
            errors.append(f"Item {i} (slug={item.get('slug', '?')}): {str(e)}")

    # Second pass: resolve fallback references
    for svc_slug, fb_slug in fallback_links:
        try:
            svc = await get_service_by_slug(session, svc_slug)
            fb = await get_service_by_slug(session, fb_slug)
            if svc and fb and svc.owner_id == admin.id:
                svc.fallback_service_id = fb.id
                await session.commit()
        except Exception as e:
            errors.append(f"Fallback link {svc_slug} -> {fb_slug}: {str(e)}")

    return {
        "groups_created": groups_created,
        "groups_updated": groups_updated,
        "created": created,
        "updated": updated,
        "errors": errors,
        "total_processed": len(services_data),
    }
