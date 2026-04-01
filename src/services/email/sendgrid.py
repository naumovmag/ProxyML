import logging
import httpx
from src.services.email.base import BaseEmailProvider, EmailMessage, EmailSendError, EmailConfigError

logger = logging.getLogger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


class SendGridEmailProvider(BaseEmailProvider):
    provider_type = "sendgrid"

    def __init__(self, api_key: str):
        self.api_key = api_key

    @classmethod
    def config_schema(cls) -> list[dict]:
        return [
            {"name": "api_key", "type": "string", "required": True, "label": "API Key", "placeholder": "SG.xxxxx", "secret": True},
        ]

    async def send(self, message: EmailMessage) -> None:
        payload = {
            "personalizations": [{"to": [{"email": message.to}]}],
            "from": {"email": message.from_address, **({"name": message.from_name} if message.from_name else {})},
            "subject": message.subject,
            "content": [{"type": "text/html", "value": message.body_html}],
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    SENDGRID_API_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    timeout=30.0,
                )
                if resp.status_code >= 400:
                    logger.error(f"SendGrid error {resp.status_code}: {resp.text}")
                    raise EmailSendError(f"SendGrid API error: {resp.status_code}")
        except httpx.HTTPError as e:
            raise EmailSendError(f"SendGrid request failed: {e}")

    async def validate_config(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.sendgrid.com/v3/scopes",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    return True
                raise EmailConfigError(f"SendGrid auth failed: {resp.status_code}")
        except httpx.HTTPError as e:
            raise EmailConfigError(f"SendGrid connection failed: {e}")
