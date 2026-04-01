import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
from src.services.email.base import BaseEmailProvider, EmailMessage, EmailSendError, EmailConfigError

logger = logging.getLogger(__name__)


class SMTPEmailProvider(BaseEmailProvider):
    provider_type = "smtp"

    def __init__(self, host: str, port: int, username: str, password: str, use_tls: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    @classmethod
    def config_schema(cls) -> list[dict]:
        return [
            {"name": "host", "type": "string", "required": True, "label": "SMTP Host", "placeholder": "smtp.gmail.com", "secret": False},
            {"name": "port", "type": "number", "required": True, "label": "SMTP Port", "placeholder": "587", "secret": False},
            {"name": "username", "type": "string", "required": True, "label": "Username", "placeholder": "user@gmail.com", "secret": False},
            {"name": "password", "type": "string", "required": True, "label": "Password", "placeholder": "app-password", "secret": True},
            {"name": "use_tls", "type": "boolean", "required": False, "label": "Use TLS", "placeholder": "", "secret": False},
        ]

    async def send(self, message: EmailMessage) -> None:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{message.from_name} <{message.from_address}>" if message.from_name else message.from_address
        msg["To"] = message.to
        msg["Subject"] = message.subject
        msg.attach(MIMEText(message.body_html, "html"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=self.use_tls,
            )
        except Exception as e:
            logger.error(f"SMTP send error: {e}")
            raise EmailSendError(f"SMTP error: {e}")

    async def validate_config(self) -> bool:
        try:
            smtp = aiosmtplib.SMTP(hostname=self.host, port=self.port)
            await smtp.connect()
            if self.use_tls:
                await smtp.starttls()
            await smtp.login(self.username, self.password)
            await smtp.quit()
            return True
        except Exception as e:
            raise EmailConfigError(f"SMTP connection failed: {e}")
