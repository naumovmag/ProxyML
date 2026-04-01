import hashlib
import logging
import secrets
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.auth_user import AuthUser
from src.models.verification_channel import VerificationChannel
from src.models.verification_code import VerificationCode

logger = logging.getLogger(__name__)

LINKING_TTL_MINUTES = 10
LINKING_PREFIX = "tglink_"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def generate_linking_code(session: AsyncSession, user_id: UUID, channel_id: UUID) -> str:
    raw_code = LINKING_PREFIX + secrets.token_urlsafe(32)
    vc = VerificationCode(
        auth_user_id=user_id,
        channel_id=channel_id,
        code_hash=_hash(raw_code),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=LINKING_TTL_MINUTES),
    )
    session.add(vc)
    await session.commit()
    return raw_code


def build_deep_link(bot_username: str, linking_code: str) -> str:
    return f"https://t.me/{bot_username}?start={linking_code}"


async def process_telegram_start(session: AsyncSession, chat_id: int, linking_code: str) -> bool:
    code_hash = _hash(linking_code)
    result = await session.execute(
        select(VerificationCode)
        .join(VerificationChannel, VerificationChannel.id == VerificationCode.channel_id)
        .where(
            VerificationCode.code_hash == code_hash,
            VerificationChannel.channel_type == "telegram",
        )
        .with_for_update(skip_locked=True)
    )
    vc = result.scalar_one_or_none()
    if not vc:
        return False
    if vc.expires_at < datetime.now(timezone.utc):
        await session.delete(vc)
        await session.commit()
        return False

    user_result = await session.execute(select(AuthUser).where(AuthUser.id == vc.auth_user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        await session.delete(vc)
        await session.commit()
        return False

    user.telegram_chat_id = str(chat_id)
    user.telegram_verified = True
    await session.delete(vc)
    await session.commit()
    logger.info(f"Telegram linked: user={user.id} chat_id={chat_id}")
    return True
