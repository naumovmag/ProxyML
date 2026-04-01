import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.api.deps import get_current_admin
from src.models.admin_user import AdminUser
from src.models.auth_system import AuthSystem
from src.models.verification_channel import VerificationChannel
from src.schemas.verification_channel import (
    VerificationChannelCreate,
    VerificationChannelUpdate,
    VerificationChannelRead,
)
from src.services.verification.registry import (
    get_all_channel_schemas,
    get_verification_provider,
)
from src.services.verification.base import (
    VerificationMessage,
    VerificationSendError,
    VerificationConfigError,
)

router = APIRouter()


class TestSendRequest(BaseModel):
    to: str


def _mask_secrets(channel: VerificationChannel) -> dict:
    from src.services.verification.registry import get_all_channel_schemas
    schemas = get_all_channel_schemas()
    ch_schema = schemas.get(channel.channel_type, {}).get("providers", {}).get(channel.provider_type, {})
    secret_fields = {f["name"] for f in ch_schema.get("config_schema", []) if f.get("secret")}
    config = dict(channel.provider_config)
    for key in secret_fields:
        if key in config and config[key]:
            config[key] = "***"
    return config


def _channel_to_read(channel: VerificationChannel) -> VerificationChannelRead:
    return VerificationChannelRead(
        id=channel.id,
        auth_system_id=channel.auth_system_id,
        channel_type=channel.channel_type,
        provider_type=channel.provider_type,
        provider_config=_mask_secrets(channel),
        is_enabled=channel.is_enabled,
        is_required=channel.is_required,
        priority=channel.priority,
        settings=channel.settings,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


async def _get_owned_system(
    system_id: uuid.UUID,
    admin: AdminUser,
    session: AsyncSession,
) -> AuthSystem:
    result = await session.execute(
        select(AuthSystem).where(AuthSystem.id == system_id, AuthSystem.owner_id == admin.id)
    )
    system = result.scalar_one_or_none()
    if not system:
        raise HTTPException(status_code=404, detail="Auth system not found")
    return system


# ---------- Справочник провайдеров ----------

@router.get("/verification-providers")
async def list_verification_providers(
    admin: AdminUser = Depends(get_current_admin),
):
    return {"providers": get_all_channel_schemas()}


# ---------- CRUD каналов ----------

@router.get(
    "/auth-systems/{system_id}/channels",
    response_model=list[VerificationChannelRead],
)
async def list_channels(
    system_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_owned_system(system_id, admin, session)
    result = await session.execute(
        select(VerificationChannel)
        .where(VerificationChannel.auth_system_id == system_id)
        .order_by(VerificationChannel.priority, VerificationChannel.created_at)
    )
    channels = result.scalars().all()
    return [_channel_to_read(ch) for ch in channels]


@router.post(
    "/auth-systems/{system_id}/channels",
    response_model=VerificationChannelRead,
    status_code=201,
)
async def create_channel(
    system_id: uuid.UUID,
    data: VerificationChannelCreate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_owned_system(system_id, admin, session)

    existing = await session.execute(
        select(VerificationChannel.id).where(
            VerificationChannel.auth_system_id == system_id,
            VerificationChannel.channel_type == data.channel_type,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Channel '{data.channel_type}' already exists for this auth system",
        )

    channel = VerificationChannel(
        auth_system_id=system_id,
        channel_type=data.channel_type,
        provider_type=data.provider_type,
        provider_config=data.provider_config,
        is_enabled=data.is_enabled,
        is_required=data.is_required,
        priority=data.priority,
        settings=data.settings,
    )
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return _channel_to_read(channel)


@router.put(
    "/auth-systems/{system_id}/channels/{channel_id}",
    response_model=VerificationChannelRead,
)
async def update_channel(
    system_id: uuid.UUID,
    channel_id: uuid.UUID,
    data: VerificationChannelUpdate,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_owned_system(system_id, admin, session)

    result = await session.execute(
        select(VerificationChannel).where(
            VerificationChannel.id == channel_id,
            VerificationChannel.auth_system_id == system_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    for field in ("provider_type", "provider_config", "is_enabled", "is_required", "priority", "settings"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(channel, field, val)

    await session.commit()
    await session.refresh(channel)
    return _channel_to_read(channel)


@router.delete(
    "/auth-systems/{system_id}/channels/{channel_id}",
    status_code=204,
)
async def delete_channel(
    system_id: uuid.UUID,
    channel_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_owned_system(system_id, admin, session)

    result = await session.execute(
        select(VerificationChannel).where(
            VerificationChannel.id == channel_id,
            VerificationChannel.auth_system_id == system_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    await session.delete(channel)
    await session.commit()


# ---------- Тестовая отправка ----------

@router.post("/auth-systems/{system_id}/channels/{channel_id}/test")
async def test_channel(
    system_id: uuid.UUID,
    channel_id: uuid.UUID,
    data: TestSendRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    system = await _get_owned_system(system_id, admin, session)

    result = await session.execute(
        select(VerificationChannel).where(
            VerificationChannel.id == channel_id,
            VerificationChannel.auth_system_id == system_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    try:
        provider = get_verification_provider(
            channel.channel_type, channel.provider_type, channel.provider_config,
        )
        await provider.send(VerificationMessage(
            to=data.to,
            code="123456",
            system_name=system.name,
        ))
        return {"ok": True, "message": f"Test message sent to {data.to}"}
    except (VerificationSendError, VerificationConfigError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------- Валидация конфига ----------

@router.post("/auth-systems/{system_id}/channels/{channel_id}/validate")
async def validate_channel_config(
    system_id: uuid.UUID,
    channel_id: uuid.UUID,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_async_session),
):
    await _get_owned_system(system_id, admin, session)

    result = await session.execute(
        select(VerificationChannel).where(
            VerificationChannel.id == channel_id,
            VerificationChannel.auth_system_id == system_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    try:
        provider = get_verification_provider(
            channel.channel_type, channel.provider_type, channel.provider_config,
        )
        await provider.validate_config()
        return {"ok": True}
    except (VerificationConfigError, VerificationSendError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
