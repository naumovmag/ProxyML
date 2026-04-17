import hashlib
import logging

from src.models.verification_channel import VerificationChannel
from src.services.verification.telegram.bot import TelegramBotProvider
from src.services.verification.telegram.polling import telegram_polling_manager

logger = logging.getLogger(__name__)


async def apply_telegram_lifecycle(channel: VerificationChannel) -> None:
    """Idempotent: configure polling or webhook based on settings.delivery_mode.

    Never raises — all errors are logged as warnings so callers (admin CRUD,
    lifespan startup) are never broken by transient Telegram API failures.
    """
    if channel.channel_type != "telegram" or not channel.is_enabled:
        await telegram_polling_manager.stop(channel.id)
        try:
            bot_token = (channel.provider_config or {}).get("bot_token", "")
            if bot_token:
                bot = TelegramBotProvider(**channel.provider_config)
                await bot.delete_webhook()
        except Exception as exc:
            logger.warning(
                "telegram lifecycle cleanup for channel %s: %s", channel.id, exc
            )
        return

    mode = (channel.settings or {}).get("delivery_mode", "polling")
    try:
        bot_token = (channel.provider_config or {}).get("bot_token", "")
        if not bot_token:
            logger.warning(
                "telegram lifecycle for channel %s: bot_token missing", channel.id
            )
            return

        bot = TelegramBotProvider(**channel.provider_config)

        if mode == "webhook":
            await telegram_polling_manager.stop(channel.id)
            url_base = (channel.settings or {}).get("webhook_base_url", "").rstrip("/")
            if not url_base.startswith("https://"):
                logger.warning(
                    "telegram lifecycle for channel %s: webhook_base_url missing or not https",
                    channel.id,
                )
                return
            secret = hashlib.sha256(
                f"{channel.id}:{bot_token}".encode()
            ).hexdigest()[:64]
            webhook_url = f"{url_base}/api/telegram/webhook/{channel.id}"
            await bot.set_webhook(webhook_url, secret_token=secret)
            # Persist the computed secret so the webhook handler can verify it
            channel.settings = {**(channel.settings or {}), "webhook_secret": secret}
            logger.info(
                "Telegram webhook set for channel %s -> %s", channel.id, webhook_url
            )
        else:
            # polling (default)
            try:
                await bot.delete_webhook()
            except Exception as exc:
                logger.warning(
                    "telegram delete_webhook for channel %s: %s", channel.id, exc
                )
            await telegram_polling_manager.start(channel.id, bot_token)
    except Exception as exc:
        logger.warning("telegram lifecycle for channel %s: %s", channel.id, exc)
