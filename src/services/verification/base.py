from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class VerificationMessage:
    to: str
    code: str
    system_name: str
    template: str | None = None
    extra: dict | None = field(default_factory=dict)


class VerificationSendError(Exception):
    pass


class VerificationConfigError(Exception):
    pass


class BaseVerificationProvider(ABC):
    channel_type: str
    provider_type: str

    @classmethod
    @abstractmethod
    def config_schema(cls) -> list[dict]:
        ...

    @abstractmethod
    async def send(self, message: VerificationMessage) -> None:
        ...

    @abstractmethod
    async def validate_config(self) -> bool:
        ...
