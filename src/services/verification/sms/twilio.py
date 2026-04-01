import logging
import httpx
from src.services.verification.base import BaseVerificationProvider, VerificationMessage, VerificationSendError, VerificationConfigError

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = "{{system_name}}: your verification code is {{code}}"


class TwilioSmsProvider(BaseVerificationProvider):
    channel_type = "sms"
    provider_type = "twilio"

    def __init__(self, **config):
        self.account_sid = config["account_sid"]
        self.auth_token = config["auth_token"]
        self.from_number = config["from_number"]

    @classmethod
    def config_schema(cls) -> list[dict]:
        return [
            {"name": "account_sid", "type": "string", "required": True, "label": "Account SID", "placeholder": "ACxxxxxxxx", "secret": False},
            {"name": "auth_token", "type": "string", "required": True, "label": "Auth Token", "placeholder": "", "secret": True},
            {"name": "from_number", "type": "string", "required": True, "label": "From Phone Number", "placeholder": "+1234567890", "secret": False},
        ]

    def _render(self, message: VerificationMessage) -> str:
        tpl = message.template or DEFAULT_TEMPLATE
        return tpl.replace("{{code}}", message.code).replace("{{system_name}}", message.system_name)

    async def send(self, message: VerificationMessage) -> None:
        text = self._render(message)
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    auth=(self.account_sid, self.auth_token),
                    data={"From": self.from_number, "To": message.to, "Body": text},
                    timeout=30.0,
                )
                if resp.status_code >= 400:
                    logger.error(f"Twilio error: {resp.status_code}")
                    raise VerificationSendError(f"Twilio API error: {resp.status_code}")
        except httpx.HTTPError as e:
            raise VerificationSendError(f"Twilio request failed: {e}")

    async def validate_config(self) -> bool:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}.json"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, auth=(self.account_sid, self.auth_token), timeout=10.0)
                if resp.status_code == 200:
                    return True
                raise VerificationConfigError(f"Twilio auth failed: {resp.status_code}")
        except httpx.HTTPError as e:
            raise VerificationConfigError(f"Twilio connection failed: {e}")
