import asyncio
import hashlib
import logging
import secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import async_session_factory
from src.models.auth_system import AuthSystem
from src.models.auth_user import AuthUser
from src.models.email_verification_token import EmailVerificationToken
from src.services.email.base import EmailMessage, EmailSendError
from src.services.email.registry import get_email_provider
from src.config import settings

logger = logging.getLogger(__name__)

DEFAULT_SUBJECT = "Verify your email for {{system_name}}"
DEFAULT_BODY = """
<div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2>Verify your email</h2>
  <p>Click the link below to verify your email for <strong>{{system_name}}</strong>:</p>
  <p><a href="{{verification_link}}" style="display:inline-block; padding:12px 24px; background:#2563eb; color:#fff; text-decoration:none; border-radius:6px;">Verify Email</a></p>
  <p>Or copy this link: {{verification_link}}</p>
  <p style="color:#666; font-size:12px;">This link expires in {{ttl_hours}} hours. If you did not register, ignore this email.</p>
</div>
"""


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _render_template(system: AuthSystem, verification_link: str, user: AuthUser) -> tuple[str, str]:
    subject = system.email_template_subject or DEFAULT_SUBJECT
    body = system.email_template_body or DEFAULT_BODY
    ttl_hours = round(system.verification_token_ttl_minutes / 60, 1)

    replacements = {
        "{{verification_link}}": verification_link,
        "{{user_email}}": user.email,
        "{{system_name}}": system.name,
        "{{ttl_hours}}": str(ttl_hours),
    }
    for key, val in replacements.items():
        subject = subject.replace(key, val)
        body = body.replace(key, val)

    return subject, body


async def _send_verification_bg(system_id: str, user_id: str) -> None:
    """Background task: generates token, sends email. Uses its own DB session."""
    try:
        async with async_session_factory() as session:
            sys_result = await session.execute(select(AuthSystem).where(AuthSystem.id == system_id))
            system = sys_result.scalar_one_or_none()
            if not system or not system.email_verification_enabled or not system.email_provider_type:
                return

            user_result = await session.execute(select(AuthUser).where(AuthUser.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                return

            # Generate token
            raw_token = secrets.token_urlsafe(48)
            token = EmailVerificationToken(
                auth_user_id=user.id,
                token_hash=_hash_token(raw_token),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=system.verification_token_ttl_minutes),
            )
            session.add(token)
            await session.commit()

            # Build verification link
            base_url = settings.server_base_url.rstrip("/") if settings.server_base_url else "http://localhost:8000"
            verification_link = f"{base_url}/api/auth/{system.slug}/verify-email?token={raw_token}"

            # Render template
            subject, body_html = _render_template(system, verification_link, user)

            # Send
            provider = get_email_provider(system.email_provider_type, system.email_provider_config or {})
            await provider.send(EmailMessage(
                to=user.email,
                subject=subject,
                body_html=body_html,
                from_address=system.email_from_address or "noreply@proxyml.local",
                from_name=system.email_from_name,
            ))
            logger.info(f"Verification email sent to {user.email} for system {system.slug}")
    except Exception as e:
        logger.error(f"Failed to send verification email: {e}")


def send_verification_email(system: AuthSystem, user: AuthUser) -> None:
    """Fire-and-forget: schedule verification email in background."""
    asyncio.get_running_loop().create_task(
        _send_verification_bg(str(system.id), str(user.id))
    )


async def verify_email_token(session: AsyncSession, token_str: str) -> AuthUser | None:
    """Verify a token, mark user as verified, return user or None."""
    token_hash = _hash_token(token_str)
    result = await session.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()
    if not token:
        return None
    if token.expires_at < datetime.now(timezone.utc):
        await session.delete(token)
        await session.commit()
        return None

    user_result = await session.execute(select(AuthUser).where(AuthUser.id == token.auth_user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        return None

    user.email_verified = True
    await session.delete(token)
    await session.commit()
    return user


async def check_rate_limit(session: AsyncSession, user_id, max_per_minute: int = 1, max_per_hour: int = 5) -> bool:
    """Return True if within rate limit, False if exceeded."""
    now = datetime.now(timezone.utc)
    minute_ago = now - timedelta(minutes=1)
    hour_ago = now - timedelta(hours=1)

    recent_minute = await session.scalar(
        select(func.count()).where(
            EmailVerificationToken.auth_user_id == user_id,
            EmailVerificationToken.created_at >= minute_ago,
        )
    )
    if (recent_minute or 0) >= max_per_minute:
        return False

    recent_hour = await session.scalar(
        select(func.count()).where(
            EmailVerificationToken.auth_user_id == user_id,
            EmailVerificationToken.created_at >= hour_ago,
        )
    )
    if (recent_hour or 0) >= max_per_hour:
        return False

    return True
