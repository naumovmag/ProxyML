import logging

from src.services.verification.base import (
    BaseVerificationProvider,
    VerificationMessage,
    VerificationSendError,
    VerificationConfigError,
)
from src.services.email.mailgun import MailgunEmailProvider
from src.services.email.base import EmailMessage, EmailSendError, EmailConfigError

logger = logging.getLogger(__name__)


class MailgunVerificationProvider(BaseVerificationProvider):
    channel_type = "email"
    provider_type = "mailgun"

    def __init__(self, **config):
        self._provider = MailgunEmailProvider(
            api_key=config["api_key"],
            domain=config["domain"],
            region=config.get("region", "us"),
        )

    @classmethod
    def config_schema(cls) -> list[dict]:
        return MailgunEmailProvider.config_schema()

    async def send(self, message: VerificationMessage) -> None:
        extra = message.extra or {}
        try:
            await self._provider.send(EmailMessage(
                to=message.to,
                subject=extra.get("subject", f"Verification code: {message.code}"),
                body_html=extra.get("body_html", f"<p>Your verification code: <strong>{message.code}</strong></p>"),
                from_address=extra.get("from_address", "noreply@proxyml.local"),
                from_name=extra.get("from_name"),
            ))
        except EmailSendError as e:
            raise VerificationSendError(str(e))

    async def validate_config(self) -> bool:
        try:
            return await self._provider.validate_config()
        except EmailConfigError as e:
            raise VerificationConfigError(str(e))
