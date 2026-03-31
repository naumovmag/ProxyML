import uuid
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError

from src.db.session import get_async_session
from src.models.auth_system import AuthSystem
from src.models.auth_user import AuthUser
from src.models.auth_refresh_token import AuthRefreshToken
from src.schemas.auth_system import (
    AuthRegisterRequest, AuthLoginRequest, AuthTokenResponse,
    AuthRefreshRequest, AuthUserRead, AuthVerifyResponse,
)
from src.utils.crypto import hash_password, verify_password

router = APIRouter()


async def _get_system(session: AsyncSession, slug: str) -> AuthSystem:
    result = await session.execute(
        select(AuthSystem).where(AuthSystem.slug == slug, AuthSystem.is_active == True)
    )
    system = result.scalar_one_or_none()
    if not system:
        raise HTTPException(status_code=404, detail="Auth system not found")
    return system


def _create_access_token(system: AuthSystem, user: AuthUser) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "sys": str(system.id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=system.access_token_ttl_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, system.jwt_secret, algorithm="HS256")


def _create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _decode_access_token(system: AuthSystem, token: str) -> dict | None:
    try:
        payload = jwt.decode(token, system.jwt_secret, algorithms=["HS256"])
        if payload.get("sys") != str(system.id):
            return None
        return payload
    except JWTError:
        return None


def _validate_custom_fields(system: AuthSystem, fields: dict) -> dict:
    """Validate custom fields against the system's registration_fields schema."""
    validated = {}
    for field_def in system.registration_fields:
        name = field_def["name"]
        ftype = field_def["type"]
        required = field_def.get("required", True)
        value = fields.get(name)

        if value is None or value == "":
            if required:
                raise HTTPException(status_code=422, detail=f"Field '{name}' is required")
            continue

        if ftype == "string" and not isinstance(value, str):
            raise HTTPException(status_code=422, detail=f"Field '{name}' must be a string")
        elif ftype == "number" and not isinstance(value, (int, float)):
            raise HTTPException(status_code=422, detail=f"Field '{name}' must be a number")
        elif ftype == "boolean" and not isinstance(value, bool):
            raise HTTPException(status_code=422, detail=f"Field '{name}' must be a boolean")
        elif ftype == "email" and (not isinstance(value, str) or "@" not in value):
            raise HTTPException(status_code=422, detail=f"Field '{name}' must be a valid email")
        elif ftype == "phone" and not isinstance(value, str):
            raise HTTPException(status_code=422, detail=f"Field '{name}' must be a string")

        validated[name] = value
    return validated


@router.post("/{slug}/register", response_model=AuthTokenResponse)
async def auth_register(
    slug: str,
    data: AuthRegisterRequest,
    session: AsyncSession = Depends(get_async_session),

):
    system = await _get_system(session, slug)

    # Check email uniqueness
    existing = await session.execute(
        select(AuthUser.id).where(
            AuthUser.auth_system_id == system.id,
            AuthUser.email == data.email.lower().strip(),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Validate custom fields
    custom_fields = _validate_custom_fields(system, data.fields)

    # Check unique fields
    for field_def in system.registration_fields:
        if field_def.get("unique") and field_def["name"] in custom_fields:
            from sqlalchemy import cast, String
            from sqlalchemy.dialects.postgresql import JSONB
            existing_unique = await session.execute(
                select(AuthUser.id).where(
                    AuthUser.auth_system_id == system.id,
                    AuthUser.custom_fields[field_def["name"]].astext == str(custom_fields[field_def["name"]]),
                )
            )
            if existing_unique.scalar_one_or_none():
                raise HTTPException(status_code=409, detail=f"Field '{field_def['name']}' value already taken")

    pw_hash = await hash_password(data.password)
    user = AuthUser(
        auth_system_id=system.id,
        email=data.email.lower().strip(),
        password_hash=pw_hash,
        custom_fields=custom_fields,
        is_active=system.users_active_by_default,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Issue tokens
    access_token = _create_access_token(system, user)
    refresh_token = _create_refresh_token()
    rt = AuthRefreshToken(
        auth_user_id=user.id,
        token_hash=_hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=system.refresh_token_ttl_days),
    )
    session.add(rt)
    await session.commit()

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=system.access_token_ttl_minutes * 60,
    )


@router.post("/{slug}/login", response_model=AuthTokenResponse)
async def auth_login(
    slug: str,
    data: AuthLoginRequest,
    session: AsyncSession = Depends(get_async_session),

):
    system = await _get_system(session, slug)

    result = await session.execute(
        select(AuthUser).where(
            AuthUser.auth_system_id == system.id,
            AuthUser.email == data.email.lower().strip(),
        )
    )
    user = result.scalar_one_or_none()
    if not user or not await verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    access_token = _create_access_token(system, user)
    refresh_token = _create_refresh_token()
    rt = AuthRefreshToken(
        auth_user_id=user.id,
        token_hash=_hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=system.refresh_token_ttl_days),
    )
    session.add(rt)
    await session.commit()

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=system.access_token_ttl_minutes * 60,
    )


@router.get("/{slug}/me", response_model=AuthUserRead)
async def auth_me(
    slug: str,
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_async_session),

):
    system = await _get_system(session, slug)

    token = authorization
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    payload = _decode_access_token(system, token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await session.execute(
        select(AuthUser).where(AuthUser.id == uuid.UUID(payload["sub"]))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


@router.post("/{slug}/refresh", response_model=AuthTokenResponse)
async def auth_refresh(
    slug: str,
    data: AuthRefreshRequest,
    session: AsyncSession = Depends(get_async_session),

):
    system = await _get_system(session, slug)

    token_hash = _hash_token(data.refresh_token)
    result = await session.execute(
        select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if rt.expires_at < datetime.now(timezone.utc):
        await session.delete(rt)
        await session.commit()
        raise HTTPException(status_code=401, detail="Refresh token expired")

    # Get user
    user_result = await session.execute(
        select(AuthUser).where(AuthUser.id == rt.auth_user_id, AuthUser.auth_system_id == system.id)
    )
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Rotate refresh token
    await session.delete(rt)
    access_token = _create_access_token(system, user)
    new_refresh_token = _create_refresh_token()
    new_rt = AuthRefreshToken(
        auth_user_id=user.id,
        token_hash=_hash_token(new_refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=system.refresh_token_ttl_days),
    )
    session.add(new_rt)
    await session.commit()

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=system.access_token_ttl_minutes * 60,
    )


@router.get("/{slug}/verify", response_model=AuthVerifyResponse)
async def auth_verify(
    slug: str,
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_async_session),

):
    system = await _get_system(session, slug)

    token = authorization
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    payload = _decode_access_token(system, token)
    if not payload:
        return AuthVerifyResponse(valid=False)

    return AuthVerifyResponse(
        valid=True,
        user_id=payload["sub"],
        email=payload.get("email"),
    )
