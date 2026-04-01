import logging

import httpx

from src.services.verification.base import (
    BaseVerificationProvider,
    VerificationConfigError,
    VerificationMessage,
    VerificationSendError,
)

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
DEFAULT_TEMPLATE = "Your verification code for {{system_name}}: {{code}}"


class TelegramBotProvider(BaseVerificationProvider):
    channel_type = "telegram"
    provider_type = "telegram_bot"

    def __init__(self, **config):
        self.bot_token = config["bot_token"]

    @classmethod
    def config_schema(cls) -> list[dict]:
        return [
            {
                "name": "bot_token",
                "type": "string",
                "required": True,
                "label": "Bot Token",
                "placeholder": "123456:ABC-DEF...",
                "secret": True,
            },
        ]

    def _render(self, message: VerificationMessage) -> str:
        tpl = message.template or DEFAULT_TEMPLATE
        return tpl.replace("{{code}}", message.code).replace(
            "{{system_name}}", message.system_name
        )

    async def send(self, message: VerificationMessage) -> None:
        text = self._render(message)
        url = f"{TELEGRAM_API}/bot{self.bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    json={
                        "chat_id": message.to,
                        "text": text,
                        "parse_mode": "HTML",
                    },
                    timeout=30.0,
                )
                if resp.status_code >= 400:
                    try:
                        data = resp.json()
                        desc = data.get("description", "Unknown error")
                    except ValueError:
                        desc = f"HTTP {resp.status_code}"
                    logger.error(f"Telegram error {resp.status_code}: {desc}")
                    raise VerificationSendError(f"Telegram API error: {desc}")
        except httpx.HTTPError as e:
            raise VerificationSendError(f"Telegram request failed: {e}")

    async def validate_config(self) -> bool:
        url = f"{TELEGRAM_API}/bot{self.bot_token}/getMe"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10.0)
                try:
                    data = resp.json()
                except ValueError:
                    raise VerificationConfigError(f"Telegram returned non-JSON response: {resp.status_code}")
                if resp.status_code == 200 and data.get("ok"):
                    return True
                raise VerificationConfigError(
                    f"Telegram bot token invalid: {data.get('description', 'Unknown')}"
                )
        except httpx.HTTPError as e:
            raise VerificationConfigError(f"Telegram connection failed: {e}")

    async def get_bot_info(self) -> dict:
        url = f"{TELEGRAM_API}/bot{self.bot_token}/getMe"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            try:
                data = resp.json()
            except ValueError:
                raise VerificationConfigError(f"Telegram returned non-JSON response: {resp.status_code}")
            if resp.status_code == 200 and data.get("ok"):
                return data["result"]
            raise VerificationConfigError(
                f"Cannot get bot info: {data.get('description', 'Unknown')}"
            )
