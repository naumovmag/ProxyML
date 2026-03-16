import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_current_admin
from src.services.service_registry import (
    list_services, get_service_by_id, get_service_by_slug, create_service, update_service, delete_service,
    FallbackValidationError,
)
from src.schemas.service import ServiceCreate, ServiceUpdate, ServiceRead
from src.models.service_group import ServiceGroup

router = APIRouter(dependencies=[Depends(get_current_admin)])

@router.get("/services", response_model=list[ServiceRead])
async def admin_list_services(session: AsyncSession = Depends(get_async_session)):
    return await list_services(session)

@router.get("/services/{service_id}", response_model=ServiceRead)
async def admin_get_service(service_id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    svc = await get_service_by_id(session, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return svc

@router.post("/services", response_model=ServiceRead, status_code=201)
async def admin_create_service(data: ServiceCreate, session: AsyncSession = Depends(get_async_session)):
    try:
        return await create_service(session, data)
    except FallbackValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/services/{service_id}", response_model=ServiceRead)
async def admin_update_service(service_id: uuid.UUID, data: ServiceUpdate, session: AsyncSession = Depends(get_async_session)):
    try:
        svc = await update_service(session, service_id, data)
    except FallbackValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return svc

@router.delete("/services/{service_id}", status_code=204)
async def admin_delete_service(service_id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    deleted = await delete_service(session, service_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Service not found")


@router.get("/services-export")
async def export_services(session: AsyncSession = Depends(get_async_session)):
    """Export all groups and services with all fields including auth tokens as JSON."""
    # Export groups
    groups_result = await session.execute(select(ServiceGroup).order_by(ServiceGroup.sort_order, ServiceGroup.name))
    groups = list(groups_result.scalars().all())
    groups_map = {g.id: g.name for g in groups}

    groups_data = [
        {"name": g.name, "description": g.description, "sort_order": g.sort_order}
        for g in groups
    ]

    # Export services
    services = await list_services(session)
    # Build id->slug map for fallback references
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
            result = await session.execute(select(ServiceGroup).where(ServiceGroup.name == name))
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
                )
                session.add(new_group)
                await session.flush()
                group_name_to_id[name] = new_group.id
                groups_created += 1
        await session.commit()

    # Load all existing groups for name->id mapping
    all_groups = await session.execute(select(ServiceGroup))
    for g in all_groups.scalars().all():
        group_name_to_id[g.name] = g.id

    # --- Import services ---
    services_data = data.get("services", data) if "services" in data else data
    if not isinstance(services_data, list):
        raise HTTPException(status_code=400, detail="Expected 'services' to be a list")

    created = 0
    updated = 0
    errors = []
    skip_keys = {"id", "created_at", "updated_at", "group_id", "group_name", "fallback_service_slug"}
    fallback_links: list[tuple[str, str]] = []  # (service_slug, fallback_slug)

    for i, item in enumerate(services_data):
        try:
            slug = item.get("slug")
            if not slug:
                errors.append(f"Item {i}: missing slug")
                continue

            # Resolve group
            group_id = None
            group_name = item.get("group_name")
            if group_name and group_name in group_name_to_id:
                group_id = group_name_to_id[group_name]

            svc_fields = {k: v for k, v in item.items() if k not in skip_keys}
            svc_fields["group_id"] = group_id
            svc_fields.pop("fallback_service_id", None)  # will be set in second pass

            existing = await get_service_by_slug(session, slug)
            if existing:
                update_data = ServiceUpdate(**svc_fields)
                await update_service(session, existing.id, update_data)
                updated += 1
            else:
                svc_data = ServiceCreate(**svc_fields)
                await create_service(session, svc_data)
                created += 1

            # Track fallback for second pass
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
            if svc and fb:
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
