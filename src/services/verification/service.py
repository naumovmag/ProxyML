import asyncio
import hashlib
import logging
import secrets
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import async_session_factory
from src.models.auth_user import AuthUser
from src.models.verification_channel import VerificationChannel
from src.models.verification_code import VerificationCode
from src.services.verification.base import VerificationMessage
from src.services.verification.registry import get_verification_provider
from src.config import settings

logger = logging.getLogger(__name__)

DEFAULT_EMAIL_SUBJECT = "Verify your email for {{system_name}}"
DEFAULT_EMAIL_BODY = """
<div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2>Verify your email</h2>
  <p>Click the link below to verify your email for <strong>{{system_name}}</strong>:</p>
  <p><a href="{{verification_link}}" style="display:inline-block; padding:12px 24px; background:#2563eb; color:#fff; text-decoration:none; border-radius:6px;">Verify Email</a></p>
  <p>Or copy this link: {{verification_link}}</p>
  <p style="color:#666; font-size:12px;">This link expires in {{ttl_hours}} hours. If you did not register, ignore this email.</p>
</div>
"""

DEFAULT_SMS_TEMPLATE = "{{system_name}}: your verification code is {{code}}"
DEFAULT_TG_TEMPLATE = "Your verification code for {{system_name}}: {{code}}"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def generate_code(length: int = 6) -> str:
    return "".join([str(secrets.randbelow(10)) for _ in range(length)])


def generate_link_token() -> str:
    return secrets.token_urlsafe(48)


def _get_code_ttl(channel: VerificationChannel) -> int:
    return channel.settings.get("code_ttl_minutes", 1440 if channel.channel_type == "email" else 10)


def _get_code_length(channel: VerificationChannel) -> int:
    return channel.settings.get("code_length", 6)


async def _send_verification_bg(channel_id: str, user_id: str, system_name: str, system_slug: str) -> None:
    try:
        async with async_session_factory() as session:
            ch_result = await session.execute(
                select(VerificationChannel).where(VerificationChannel.id == channel_id)
            )
            channel = ch_result.scalar_one_or_none()
            if not channel or not channel.is_enabled:
                return

            user_result = await session.execute(select(AuthUser).where(AuthUser.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user or not user.is_active:
                return

            # Determine recipient
            recipient = _get_recipient(channel, user)
            if not recipient:
                logger.warning(f"No recipient for channel {channel.channel_type} user {user.id}")
                return

            ttl_minutes = _get_code_ttl(channel)
            verification_mode = channel.settings.get("verification_mode", "code")

            # Generate code or link token
            if channel.channel_type == "email" and verification_mode == "link":
                raw_code = generate_link_token()
            else:
                raw_code = generate_code(_get_code_length(channel))

            # Delete old codes for this user+channel before creating new
            from sqlalchemy import delete as sa_delete
            await session.execute(
                sa_delete(VerificationCode).where(
                    VerificationCode.auth_user_id == user.id,
                    VerificationCode.channel_id == channel.id,
                )
            )

            # Save verification code
            vc = VerificationCode(
                auth_user_id=user.id,
                channel_id=channel.id,
                code_hash=_hash(raw_code),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
            )
            session.add(vc)
            await session.commit()

            # Build message
            msg = _build_message(channel, user, raw_code, system_name, system_slug, ttl_minutes)

            # Send
            provider = get_verification_provider(channel.channel_type, channel.provider_type, channel.provider_config)
            await provider.send(msg)
            logger.info(f"Verification sent via {channel.channel_type}/{channel.provider_type} to {recipient}")

    except Exception as e:
        logger.error(f"Failed to send verification (channel={channel_id}): {e}")


def _get_recipient(channel: VerificationChannel, user: AuthUser) -> str | None:
    if channel.channel_type == "email":
        return user.email
    elif channel.channel_type == "sms":
        return user.phone
    elif channel.channel_type == "telegram":
        return user.telegram_chat_id
    return None


def _build_message(
    channel: VerificationChannel,
    user: AuthUser,
    raw_code: str,
    system_name: str,
    system_slug: str,
    ttl_minutes: int,
) -> VerificationMessage:
    s = channel.settings
    recipient = _get_recipient(channel, user)
    if not recipient:
        raise ValueError(f"No recipient for channel {channel.channel_type}, user {user.id}")

    if channel.channel_type == "email":
        verification_mode = s.get("verification_mode", "link")
        if verification_mode == "link":
            base_url = (settings.server_base_url or "http://localhost:8000").rstrip("/")
            verification_link = f"{base_url}/api/auth/{system_slug}/verify-email?token={raw_code}"
            ttl_hours = round(ttl_minutes / 60, 1)

            subject = s.get("template_subject") or DEFAULT_EMAIL_SUBJECT
            body = s.get("template_body") or DEFAULT_EMAIL_BODY

            replacements = {
                "{{verification_link}}": verification_link,
                "{{user_email}}": user.email,
                "{{system_name}}": system_name,
                "{{ttl_hours}}": str(ttl_hours),
                "{{code}}": raw_code,
            }
            for key, val in replacements.items():
                subject = subject.replace(key, val)
                body = body.replace(key, val)

            return VerificationMessage(
                to=recipient,
                code=raw_code,
                system_name=system_name,
                extra={
                    "subject": subject,
                    "body_html": body,
                    "from_address": s.get("from_address") or "noreply@proxyml.local",
                    "from_name": s.get("from_name") or None,
                },
            )
        else:
            subject = s.get("template_subject") or f"{system_name}: your verification code"
            body = f"<p>Your verification code: <strong>{raw_code}</strong></p>"
            return VerificationMessage(
                to=recipient,
                code=raw_code,
                system_name=system_name,
                extra={
                    "subject": subject,
                    "body_html": body,
                    "from_address": s.get("from_address") or "noreply@proxyml.local",
                    "from_name": s.get("from_name") or None,
                },
            )

    elif channel.channel_type == "sms":
        template = s.get("message_template") or DEFAULT_SMS_TEMPLATE
        return VerificationMessage(to=recipient, code=raw_code, system_name=system_name, template=template)

    elif channel.channel_type == "telegram":
        template = s.get("message_template") or DEFAULT_TG_TEMPLATE
        return VerificationMessage(to=recipient, code=raw_code, system_name=system_name, template=template)

    return VerificationMessage(to=recipient, code=raw_code, system_name=system_name)


def send_verification(channel: VerificationChannel, user: AuthUser, system_name: str, system_slug: str) -> None:
    asyncio.get_running_loop().create_task(
        _send_verification_bg(str(channel.id), str(user.id), system_name, system_slug)
    )


async def send_all_verifications(session: AsyncSession, auth_system_id: UUID, user: AuthUser, system_name: str, system_slug: str) -> None:
    result = await session.execute(
        select(VerificationChannel).where(
            VerificationChannel.auth_system_id == auth_system_id,
            VerificationChannel.is_enabled == True,
        ).order_by(VerificationChannel.priority)
    )
    channels = result.scalars().all()
    for channel in channels:
        if _get_recipient(channel, user):
            send_verification(channel, user, system_name, system_slug)


async def verify_code(session: AsyncSession, channel_id: UUID, code_str: str) -> AuthUser | None:
    code_hash = _hash(code_str)
    result = await session.execute(
        select(VerificationCode).where(
            VerificationCode.channel_id == channel_id,
            VerificationCode.code_hash == code_hash,
        ).with_for_update(skip_locked=True)
    )
    vc = result.scalar_one_or_none()
    if not vc:
        return None
    if vc.expires_at < datetime.now(timezone.utc):
        await session.delete(vc)
        await session.commit()
        return None

    user_result = await session.execute(select(AuthUser).where(AuthUser.id == vc.auth_user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        return None

    # Get channel to know the type
    ch_result = await session.execute(select(VerificationChannel).where(VerificationChannel.id == channel_id))
    channel = ch_result.scalar_one_or_none()
    if channel:
        if channel.channel_type == "email":
            user.email_verified = True
        elif channel.channel_type == "sms":
            user.phone_verified = True
        elif channel.channel_type == "telegram":
            user.telegram_verified = True

    await session.delete(vc)
    await session.commit()
    return user


async def check_all_verified(session: AsyncSession, auth_system_id: UUID, user: AuthUser) -> bool:
    result = await session.execute(
        select(VerificationChannel).where(
            VerificationChannel.auth_system_id == auth_system_id,
            VerificationChannel.is_enabled == True,
            VerificationChannel.is_required == True,
        )
    )
    channels = result.scalars().all()
    for channel in channels:
        if channel.channel_type == "email" and not user.email_verified:
            return False
        if channel.channel_type == "sms" and not user.phone_verified:
            return False
        if channel.channel_type == "telegram" and not user.telegram_verified:
            return False
    return True


async def check_rate_limit(session: AsyncSession, user_id: UUID, channel_id: UUID, max_per_minute: int = 1, max_per_hour: int = 5) -> bool:
    now = datetime.now(timezone.utc)
    minute_ago = now - timedelta(minutes=1)
    hour_ago = now - timedelta(hours=1)

    recent_minute = await session.scalar(
        select(func.count()).where(
            VerificationCode.auth_user_id == user_id,
            VerificationCode.channel_id == channel_id,
            VerificationCode.created_at >= minute_ago,
        )
    )
    if (recent_minute or 0) >= max_per_minute:
        return False

    recent_hour = await session.scalar(
        select(func.count()).where(
            VerificationCode.auth_user_id == user_id,
            VerificationCode.channel_id == channel_id,
            VerificationCode.created_at >= hour_ago,
        )
    )
    if (recent_hour or 0) >= max_per_hour:
        return False

    return True
