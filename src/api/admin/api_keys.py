import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_current_admin
from src.services.api_key_service import list_api_keys, create_api_key, update_api_key, delete_api_key, toggle_api_key, get_keys_for_service
from src.schemas.api_key import ApiKeyCreate, ApiKeyUpdate, ApiKeyRead, ApiKeyCreated
from src.models.admin_user import AdminUser

router = APIRouter()


@router.get("/api-keys", response_model=list[ApiKeyRead])
async def admin_list_keys(
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    return await list_api_keys(session, owner_id=admin.id)


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=201)
async def admin_create_key(
    data: ApiKeyCreate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    api_key, raw_key = await create_api_key(session, data, owner_id=admin.id)
    result = ApiKeyRead.model_validate(api_key)
    return ApiKeyCreated(**result.model_dump(), raw_key=raw_key)


@router.put("/api-keys/{key_id}", response_model=ApiKeyRead)
async def admin_update_key(
    key_id: uuid.UUID,
    data: ApiKeyUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    key = await update_api_key(session, key_id, data, owner_id=admin.id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    return key


@router.get("/api-keys/by-service/{slug}", response_model=list[ApiKeyRead])
async def admin_keys_for_service(
    slug: str,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    return await get_keys_for_service(session, slug, owner_id=admin.id)


@router.delete("/api-keys/{key_id}", status_code=204)
async def admin_delete_key(
    key_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    deleted = await delete_api_key(session, key_id, owner_id=admin.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="API key not found")


@router.patch("/api-keys/{key_id}/toggle", response_model=ApiKeyRead)
async def admin_toggle_key(
    key_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    key = await toggle_api_key(session, key_id, owner_id=admin.id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    return key
