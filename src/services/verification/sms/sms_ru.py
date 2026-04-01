import logging
import httpx
from src.services.verification.base import BaseVerificationProvider, VerificationMessage, VerificationSendError, VerificationConfigError

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = "{{system_name}}: your code is {{code}}"


class SmsRuProvider(BaseVerificationProvider):
    channel_type = "sms"
    provider_type = "sms_ru"

    def __init__(self, **config):
        self.api_id = config["api_id"]
        self.from_name = config.get("from_name")

    @classmethod
    def config_schema(cls) -> list[dict]:
        return [
            {"name": "api_id", "type": "string", "required": True, "label": "API ID", "placeholder": "", "secret": True},
            {"name": "from_name", "type": "string", "required": False, "label": "Sender Name", "placeholder": "MyApp", "secret": False},
        ]

    def _render(self, message: VerificationMessage) -> str:
        tpl = message.template or DEFAULT_TEMPLATE
        return tpl.replace("{{code}}", message.code).replace("{{system_name}}", message.system_name)

    async def send(self, message: VerificationMessage) -> None:
        text = self._render(message)
        params = {
            "api_id": self.api_id,
            "to": message.to,
            "msg": text,
            "json": "1",
        }
        if self.from_name:
            params["from"] = self.from_name
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://sms.ru/sms/send", params=params, timeout=30.0)
                try:
                    data = resp.json()
                except ValueError:
                    raise VerificationSendError(f"SMS.ru returned non-JSON response: {resp.status_code}")
                if data.get("status") != "OK":
                    logger.error(f"SMS.ru send failed: {data.get('status_text', 'Unknown')}")
                    raise VerificationSendError(f"SMS.ru error: {data.get('status_text', 'Unknown')}")
        except httpx.HTTPError as e:
            raise VerificationSendError(f"SMS.ru request failed: {e}")

    async def validate_config(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://sms.ru/my/balance",
                    params={"api_id": self.api_id, "json": "1"},
                    timeout=10.0,
                )
                try:
                    data = resp.json()
                except ValueError:
                    raise VerificationConfigError(f"SMS.ru returned non-JSON response: {resp.status_code}")
                if data.get("status") == "OK":
                    return True
                raise VerificationConfigError(f"SMS.ru auth failed: {data.get('status_text', 'Unknown')}")
        except httpx.HTTPError as e:
            raise VerificationConfigError(f"SMS.ru connection failed: {e}")
