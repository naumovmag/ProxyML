import logging

from src.services.verification.base import (
    BaseVerificationProvider,
    VerificationMessage,
    VerificationSendError,
    VerificationConfigError,
)
from src.services.email.smtp import SMTPEmailProvider
from src.services.email.base import EmailMessage, EmailSendError, EmailConfigError

logger = logging.getLogger(__name__)


class SmtpVerificationProvider(BaseVerificationProvider):
    channel_type = "email"
    provider_type = "smtp"

    def __init__(self, **config):
        self._provider = SMTPEmailProvider(
            host=config["host"],
            port=int(config["port"]),
            username=config["username"],
            password=config["password"],
            use_tls=config.get("use_tls", True),
        )

    @classmethod
    def config_schema(cls) -> list[dict]:
        return SMTPEmailProvider.config_schema()

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
