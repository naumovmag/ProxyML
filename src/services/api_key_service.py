import uuid
from datetime import datetime, timezone
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.api_key import ApiKey
from src.schemas.api_key import ApiKeyCreate, ApiKeyUpdate
from src.utils.crypto import generate_api_key, hash_api_key, get_key_prefix

async def list_api_keys(session: AsyncSession) -> list[ApiKey]:
    result = await session.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    return list(result.scalars().all())

async def create_api_key(session: AsyncSession, data: ApiKeyCreate) -> tuple[ApiKey, str]:
    raw_key = generate_api_key()
    api_key = ApiKey(
        name=data.name,
        key_hash=hash_api_key(raw_key),
        key_prefix=get_key_prefix(raw_key),
        allowed_services=data.allowed_services,
        rate_limit_rpm=data.rate_limit_rpm,
        expires_at=data.expires_at,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return api_key, raw_key

async def validate_api_key(session: AsyncSession, raw_key: str) -> ApiKey | None:
    key_hash = hash_api_key(raw_key)
    result = await session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True))
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        return None
    # Update last_used_at
    api_key.last_used_at = datetime.now(timezone.utc)
    await session.commit()
    return api_key

async def update_api_key(session: AsyncSession, key_id: uuid.UUID, data: ApiKeyUpdate) -> ApiKey | None:
    result = await session.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None
    if data.name is not None:
        api_key.name = data.name
    if data.clear_allowed_services:
        api_key.allowed_services = None
    elif data.allowed_services is not None:
        api_key.allowed_services = data.allowed_services
    if data.rate_limit_rpm is not None:
        api_key.rate_limit_rpm = data.rate_limit_rpm
    if data.expires_at is not None:
        api_key.expires_at = data.expires_at
    await session.commit()
    await session.refresh(api_key)
    return api_key


async def get_keys_for_service(session: AsyncSession, slug: str) -> list[ApiKey]:
    """Get all active keys that have access to a given service (by slug)."""
    result = await session.execute(select(ApiKey).where(ApiKey.is_active == True))
    keys = result.scalars().all()
    return [k for k in keys if k.allowed_services is None or slug in k.allowed_services]


async def delete_api_key(session: AsyncSession, key_id: uuid.UUID) -> bool:
    result = await session.execute(delete(ApiKey).where(ApiKey.id == key_id))
    await session.commit()
    return result.rowcount > 0

async def toggle_api_key(session: AsyncSession, key_id: uuid.UUID) -> ApiKey | None:
    result = await session.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None
    api_key.is_active = not api_key.is_active
    await session.commit()
    await session.refresh(api_key)
    return api_key
