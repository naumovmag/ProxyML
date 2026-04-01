import uuid
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
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
    AuthUpdateProfileRequest, AuthChangePasswordRequest, AuthLogoutRequest,
)
from src.utils.crypto import hash_password, verify_password
from src.services.email.verification import send_verification_email, verify_email_token, check_rate_limit
from src.models.verification_channel import VerificationChannel
from src.schemas.verification_channel import VerifyCodeRequest, ResendCodeRequest, TelegramLinkResponse
from src.services.verification.service import send_all_verifications, verify_code as verify_channel_code, check_all_verified, check_rate_limit as channel_rate_limit, send_verification
from src.services.verification.telegram.linking import generate_linking_code, build_deep_link

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

    # Check if verification_channels are configured
    ch_result = await session.execute(
        select(VerificationChannel.id).where(
            VerificationChannel.auth_system_id == system.id,
            VerificationChannel.is_enabled == True,
        )
    )
    has_channels = ch_result.scalar_one_or_none() is not None

    if has_channels:
        # Use new multi-channel verification
        await send_all_verifications(session, system.id, user, system.name, system.slug)
    elif system.email_verification_enabled:
        # Backward compat: use legacy email verification
        send_verification_email(system, user)

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
    # Check verification: new channels or legacy
    has_required_channels_result = await session.execute(
        select(VerificationChannel.id).where(
            VerificationChannel.auth_system_id == system.id,
            VerificationChannel.is_enabled == True,
            VerificationChannel.is_required == True,
        )
    )
    if has_required_channels_result.scalar_one_or_none() is not None:
        # New system: check all required channels
        if not await check_all_verified(session, system.id, user):
            raise HTTPException(status_code=403, detail="Verification required. Please complete all required verifications.")
    elif system.require_email_verification and not user.email_verified:
        # Legacy: check email only
        raise HTTPException(status_code=403, detail="Email not verified. Please check your inbox.")

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


@router.patch("/{slug}/me", response_model=AuthUserRead)
async def auth_update_profile(
    slug: str,
    data: AuthUpdateProfileRequest,
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_async_session),
):
    system = await _get_system(session, slug)
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization
    payload = _decode_access_token(system, token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await session.execute(select(AuthUser).where(AuthUser.id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    custom_fields = _validate_custom_fields(system, data.fields)
    user.custom_fields = {**user.custom_fields, **custom_fields}
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/{slug}/change-password")
async def auth_change_password(
    slug: str,
    data: AuthChangePasswordRequest,
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_async_session),
):
    system = await _get_system(session, slug)
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization
    payload = _decode_access_token(system, token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await session.execute(select(AuthUser).where(AuthUser.id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    if not await verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Old password is incorrect")

    user.password_hash = await hash_password(data.new_password)
    await session.commit()
    return {"ok": True}


@router.post("/{slug}/logout")
async def auth_logout(
    slug: str,
    data: AuthLogoutRequest,
    session: AsyncSession = Depends(get_async_session),
):
    await _get_system(session, slug)
    token_hash = _hash_token(data.refresh_token)
    result = await session.execute(
        select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()
    if rt:
        await session.delete(rt)
        await session.commit()
    return {"ok": True}


@router.get("/{slug}/verify-email", include_in_schema=False)
async def auth_verify_email(
    slug: str,
    token: str,
    session: AsyncSession = Depends(get_async_session),
):
    system = await _get_system(session, slug)
    user = await verify_email_token(session, token)
    if not user:
        return HTMLResponse("<h2>Invalid or expired verification link</h2>", status_code=400)
    if system.verification_redirect_url:
        sep = "&" if "?" in system.verification_redirect_url else "?"
        return RedirectResponse(f"{system.verification_redirect_url}{sep}verified=true")
    return HTMLResponse("<div style='font-family:sans-serif;text-align:center;padding:60px'><h2>Email verified successfully!</h2><p>You can close this page.</p></div>")


@router.post("/{slug}/resend-verification")
async def auth_resend_verification(
    slug: str,
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_async_session),
):
    system = await _get_system(session, slug)
    if not system.email_verification_enabled:
        raise HTTPException(status_code=400, detail="Email verification is not enabled")

    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization
    payload = _decode_access_token(system, token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_result = await session.execute(select(AuthUser).where(AuthUser.id == uuid.UUID(payload["sub"])))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.email_verified:
        return {"ok": True, "message": "Already verified"}

    if not await check_rate_limit(session, user.id):
        raise HTTPException(status_code=429, detail="Too many verification emails. Please wait.")

    send_verification_email(system, user)
    return {"ok": True, "message": "Verification email sent"}


@router.post("/{slug}/verify-code")
async def auth_verify_code(
    slug: str,
    data: VerifyCodeRequest,
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_async_session),
):
    system = await _get_system(session, slug)
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization
    payload = _decode_access_token(system, token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Find channel
    ch_result = await session.execute(
        select(VerificationChannel).where(
            VerificationChannel.auth_system_id == system.id,
            VerificationChannel.channel_type == data.channel_type,
            VerificationChannel.is_enabled == True,
        )
    )
    channel = ch_result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=400, detail=f"No active {data.channel_type} verification channel")

    user = await verify_channel_code(session, channel.id, data.code)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    return {"ok": True, "channel_type": data.channel_type, "verified": True}


@router.get("/{slug}/verification-status")
async def auth_verification_status(
    slug: str,
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_async_session),
):
    system = await _get_system(session, slug)
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization
    payload = _decode_access_token(system, token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_result = await session.execute(select(AuthUser).where(AuthUser.id == uuid.UUID(payload["sub"])))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    channels_result = await session.execute(
        select(VerificationChannel).where(
            VerificationChannel.auth_system_id == system.id,
            VerificationChannel.is_enabled == True,
        ).order_by(VerificationChannel.priority)
    )
    channels = channels_result.scalars().all()

    result = []
    for ch in channels:
        entry = {
            "type": ch.channel_type,
            "required": ch.is_required,
            "verified": False,
        }
        if ch.channel_type == "email":
            entry["verified"] = user.email_verified
        elif ch.channel_type == "sms":
            entry["verified"] = user.phone_verified
        elif ch.channel_type == "telegram":
            entry["verified"] = user.telegram_verified
            if not user.telegram_chat_id:
                bot_username = ch.settings.get("bot_username", "")
                if bot_username:
                    entry["needs_linking"] = True
        result.append(entry)

    return {"channels": result}


@router.post("/{slug}/resend-code")
async def auth_resend_code(
    slug: str,
    data: ResendCodeRequest,
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_async_session),
):
    system = await _get_system(session, slug)
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization
    payload = _decode_access_token(system, token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_result = await session.execute(select(AuthUser).where(AuthUser.id == uuid.UUID(payload["sub"])))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    ch_result = await session.execute(
        select(VerificationChannel).where(
            VerificationChannel.auth_system_id == system.id,
            VerificationChannel.channel_type == data.channel_type,
            VerificationChannel.is_enabled == True,
        )
    )
    channel = ch_result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=400, detail=f"No active {data.channel_type} verification channel")

    if not await channel_rate_limit(session, user.id, channel.id):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait.")

    send_verification(channel, user, system.name, system.slug)
    return {"ok": True, "message": f"Verification code sent via {data.channel_type}"}


@router.post("/{slug}/telegram-link", response_model=TelegramLinkResponse)
async def auth_telegram_link(
    slug: str,
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_async_session),
):
    system = await _get_system(session, slug)
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization
    payload = _decode_access_token(system, token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_result = await session.execute(select(AuthUser).where(AuthUser.id == uuid.UUID(payload["sub"])))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    ch_result = await session.execute(
        select(VerificationChannel).where(
            VerificationChannel.auth_system_id == system.id,
            VerificationChannel.channel_type == "telegram",
            VerificationChannel.is_enabled == True,
        )
    )
    channel = ch_result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=400, detail="No active Telegram verification channel")

    bot_username = channel.settings.get("bot_username", "")
    if not bot_username:
        raise HTTPException(status_code=400, detail="Telegram bot username not configured")

    code = await generate_linking_code(session, user.id, channel.id)
    deep_link = build_deep_link(bot_username, code)
    return TelegramLinkResponse(deep_link=deep_link, expires_in=600)


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

    user_result = await session.execute(select(AuthUser).where(AuthUser.id == uuid.UUID(payload["sub"])))
    user = user_result.scalar_one_or_none()

    return AuthVerifyResponse(
        valid=True,
        user_id=payload["sub"],
        email=payload.get("email"),
        email_verified=user.email_verified if user else None,
        phone_verified=user.phone_verified if user else None,
        telegram_verified=user.telegram_verified if user else None,
    )


def _build_openapi(system, base_path: str) -> dict:
    """Build OpenAPI 3.0 spec dynamically from auth system config."""
    type_map = {"string": "string", "email": "string", "phone": "string", "number": "number", "boolean": "boolean"}

    # Build fields schema for register
    fields_properties = {}
    fields_required = []
    for f in system.registration_fields:
        fields_properties[f["name"]] = {"type": type_map.get(f["type"], "string")}
        if f.get("required"):
            fields_required.append(f["name"])

    register_schema = {
        "type": "object",
        "required": ["email", "password"],
        "properties": {
            "email": {"type": "string", "format": "email"},
            "password": {"type": "string", "minLength": 6},
        },
    }
    if fields_properties:
        register_schema["properties"]["fields"] = {
            "type": "object",
            "properties": fields_properties,
            **({"required": fields_required} if fields_required else {}),
        }

    token_response = {
        "type": "object",
        "properties": {
            "access_token": {"type": "string"},
            "refresh_token": {"type": "string"},
            "token_type": {"type": "string", "example": "bearer"},
            "expires_in": {"type": "integer", "example": system.access_token_ttl_minutes * 60},
        },
    }

    user_response = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "email": {"type": "string"},
            "custom_fields": {"type": "object"},
            "is_active": {"type": "boolean"},
            "created_at": {"type": "string", "format": "date-time"},
        },
    }

    bearer = {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}

    return {
        "openapi": "3.0.3",
        "info": {"title": system.name, "version": "1.0.0", "description": f"Auth system API for **{system.name}**"},
        "servers": [{"url": base_path}],
        "components": {
            "securitySchemes": bearer,
            "schemas": {
                "RegisterRequest": register_schema,
                "LoginRequest": {
                    "type": "object",
                    "required": ["email", "password"],
                    "properties": {
                        "email": {"type": "string", "format": "email"},
                        "password": {"type": "string"},
                    },
                },
                "TokenResponse": token_response,
                "RefreshRequest": {
                    "type": "object",
                    "required": ["refresh_token"],
                    "properties": {"refresh_token": {"type": "string"}},
                },
                "UserResponse": user_response,
                "UpdateProfileRequest": {
                    "type": "object",
                    "properties": {"fields": {"type": "object", "properties": fields_properties}},
                },
                "VerifyResponse": {
                    "type": "object",
                    "properties": {
                        "valid": {"type": "boolean"},
                        "user_id": {"type": "string"},
                        "email": {"type": "string"},
                    },
                },
            },
        },
        "paths": {
            "/register": {
                "post": {
                    "summary": "Register",
                    "description": "Register a new user and receive tokens.",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/RegisterRequest"}}}},
                    "responses": {"200": {"description": "Success", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/TokenResponse"}}}}},
                },
            },
            "/login": {
                "post": {
                    "summary": "Login",
                    "description": "Authenticate by email and password.",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/LoginRequest"}}}},
                    "responses": {"200": {"description": "Success", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/TokenResponse"}}}}},
                },
            },
            "/refresh": {
                "post": {
                    "summary": "Refresh Token",
                    "description": "Exchange refresh token for new access + refresh tokens.",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/RefreshRequest"}}}},
                    "responses": {"200": {"description": "Success", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/TokenResponse"}}}}},
                },
            },
            "/verify": {
                "get": {
                    "summary": "Verify Token",
                    "description": "Check if access token is valid.",
                    "security": [{"bearerAuth": []}],
                    "responses": {"200": {"description": "Success", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/VerifyResponse"}}}}},
                },
            },
            "/me": {
                "get": {
                    "summary": "Get Current User",
                    "description": "Get authenticated user profile.",
                    "security": [{"bearerAuth": []}],
                    "responses": {"200": {"description": "Success", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/UserResponse"}}}}},
                },
                "patch": {
                    "summary": "Update Profile",
                    "description": "Update custom fields of the authenticated user.",
                    "security": [{"bearerAuth": []}],
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/UpdateProfileRequest"}}}},
                    "responses": {"200": {"description": "Success", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/UserResponse"}}}}},
                },
            },
            "/change-password": {
                "post": {
                    "summary": "Change Password",
                    "description": "Change password for the authenticated user.",
                    "security": [{"bearerAuth": []}],
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {
                        "type": "object", "required": ["old_password", "new_password"],
                        "properties": {"old_password": {"type": "string"}, "new_password": {"type": "string", "minLength": 6}},
                    }}}},
                    "responses": {"200": {"description": "Success"}},
                },
            },
            "/logout": {
                "post": {
                    "summary": "Logout",
                    "description": "Invalidate refresh token.",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {
                        "type": "object", "required": ["refresh_token"],
                        "properties": {"refresh_token": {"type": "string"}},
                    }}}},
                    "responses": {"200": {"description": "Success"}},
                },
            },
        },
    }


@router.get("/{slug}/openapi.json", include_in_schema=False)
async def auth_openapi(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    system = await _get_system(session, slug)
    # Respect X-Forwarded-Proto from reverse proxy (nginx ingress terminates TLS)
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.base_url.hostname))
    base_path = f"{proto}://{host}/api/auth/{slug}"
    return JSONResponse(_build_openapi(system, base_path))


@router.get("/{slug}/docs", include_in_schema=False)
async def auth_docs(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
):
    system = await _get_system(session, slug)
    html = f"""<!DOCTYPE html>
<html><head>
<title>{system.name} — API Docs</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head><body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({{url:"./openapi.json",dom_id:"#swagger-ui",presets:[SwaggerUIBundle.presets.apis,SwaggerUIBundle.SwaggerUIStandalonePreset],layout:"BaseLayout"}})</script>
</body></html>"""
    return HTMLResponse(html)
