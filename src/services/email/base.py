from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EmailMessage:
    to: str
    subject: str
    body_html: str
    from_address: str
    from_name: str | None = None


class EmailSendError(Exception):
    pass


class EmailConfigError(Exception):
    pass


class BaseEmailProvider(ABC):
    """Abstract base for all email providers."""

    provider_type: str

    @classmethod
    @abstractmethod
    def config_schema(cls) -> list[dict]:
        """Return JSON-serializable schema for provider config fields.
        Each item: {"name", "type", "required", "label", "placeholder", "secret"}
        """
        ...

    @abstractmethod
    async def send(self, message: EmailMessage) -> None:
        """Send an email. Raises EmailSendError on failure."""
        ...

    @abstractmethod
    async def validate_config(self) -> bool:
        """Test that config is valid. Raises EmailConfigError on failure."""
        ...
