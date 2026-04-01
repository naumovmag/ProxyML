import logging
import httpx
from src.services.email.base import BaseEmailProvider, EmailMessage, EmailSendError, EmailConfigError

logger = logging.getLogger(__name__)


class MailgunEmailProvider(BaseEmailProvider):
    provider_type = "mailgun"

    def __init__(self, api_key: str, domain: str, region: str = "us"):
        self.api_key = api_key
        self.domain = domain
        self.base_url = f"https://api.eu.mailgun.net" if region == "eu" else "https://api.mailgun.net"

    @classmethod
    def config_schema(cls) -> list[dict]:
        return [
            {"name": "api_key", "type": "string", "required": True, "label": "API Key", "placeholder": "key-xxxxx", "secret": True},
            {"name": "domain", "type": "string", "required": True, "label": "Domain", "placeholder": "mg.example.com", "secret": False},
            {"name": "region", "type": "string", "required": False, "label": "Region (us/eu)", "placeholder": "us", "secret": False},
        ]

    async def send(self, message: EmailMessage) -> None:
        from_str = f"{message.from_name} <{message.from_address}>" if message.from_name else message.from_address
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/v3/{self.domain}/messages",
                    auth=("api", self.api_key),
                    data={"from": from_str, "to": message.to, "subject": message.subject, "html": message.body_html},
                    timeout=30.0,
                )
                if resp.status_code >= 400:
                    logger.error(f"Mailgun error {resp.status_code}: {resp.text}")
                    raise EmailSendError(f"Mailgun API error: {resp.status_code}")
        except httpx.HTTPError as e:
            raise EmailSendError(f"Mailgun request failed: {e}")

    async def validate_config(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/v3/domains/{self.domain}",
                    auth=("api", self.api_key),
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    return True
                raise EmailConfigError(f"Mailgun auth failed: {resp.status_code}")
        except httpx.HTTPError as e:
            raise EmailConfigError(f"Mailgun connection failed: {e}")
