import hashlib
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_async_session
from src.models.verification_channel import VerificationChannel
from src.services.verification.telegram.linking import process_telegram_start

logger = logging.getLogger(__name__)

router = APIRouter()


def _compute_webhook_secret(channel_id: str, bot_token: str) -> str:
    """Deterministic secret derived from channel_id + bot_token."""
    return hashlib.sha256(f"{channel_id}:{bot_token}".encode()).hexdigest()[:64]


@router.post("/telegram/webhook/{channel_id}")
async def telegram_webhook(
    channel_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """Handle Telegram Bot API webhook updates for account linking."""
    # Verify channel exists and is telegram type
    result = await session.execute(
        select(VerificationChannel).where(
            VerificationChannel.id == channel_id,
            VerificationChannel.channel_type == "telegram",
            VerificationChannel.is_enabled == True,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        return JSONResponse({"ok": True})

    # Verify webhook authenticity via secret token
    expected_secret = _compute_webhook_secret(str(channel_id), channel.provider_config.get("bot_token", ""))
    provided_secret = request.headers.get("x-telegram-bot-api-secret-token", "")
    if provided_secret != expected_secret:
        logger.warning(f"Telegram webhook: invalid secret for channel {channel_id}")
        return JSONResponse({"ok": True})

    try:
        update = await request.json()
    except Exception:
        return JSONResponse({"ok": True})

    # Process /start command with linking code
    message = update.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")

    if not chat_id or not text.startswith("/start "):
        return JSONResponse({"ok": True})

    linking_code = text[7:].strip()
    if not linking_code:
        return JSONResponse({"ok": True})

    try:
        success = await process_telegram_start(session, chat_id, linking_code)
        if success:
            from src.services.verification.telegram.bot import TelegramBotProvider
            bot = TelegramBotProvider(**channel.provider_config)
            from src.services.verification.base import VerificationMessage
            await bot.send(VerificationMessage(
                to=str(chat_id),
                code="",
                system_name="",
                template="Account linked successfully! You will receive verification codes here.",
            ))
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")

    return JSONResponse({"ok": True})
