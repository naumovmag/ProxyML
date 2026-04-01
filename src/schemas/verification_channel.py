import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

VALID_PROVIDERS = {
    "email": {"smtp", "sendgrid", "mailgun"},
    "sms": {"twilio", "sms_ru"},
    "telegram": {"telegram_bot"},
}


class VerificationChannelCreate(BaseModel):
    channel_type: str = Field(..., pattern=r"^(email|sms|telegram)$")
    provider_type: str = Field(..., max_length=50)
    provider_config: dict = {}
    is_enabled: bool = True
    is_required: bool = False
    priority: int = 0
    settings: dict = {}

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, v, info):
        channel_type = info.data.get("channel_type")
        if channel_type and channel_type in VALID_PROVIDERS:
            if v not in VALID_PROVIDERS[channel_type]:
                valid = ", ".join(sorted(VALID_PROVIDERS[channel_type]))
                raise ValueError(f"Invalid provider '{v}' for channel '{channel_type}'. Valid: {valid}")
        return v


class VerificationChannelUpdate(BaseModel):
    provider_type: str | None = Field(default=None, max_length=50)
    provider_config: dict | None = None
    is_enabled: bool | None = None
    is_required: bool | None = None
    priority: int | None = None
    settings: dict | None = None


class VerificationChannelRead(BaseModel):
    id: uuid.UUID
    auth_system_id: uuid.UUID
    channel_type: str
    provider_type: str
    provider_config: dict
    is_enabled: bool
    is_required: bool
    priority: int
    settings: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VerifyCodeRequest(BaseModel):
    channel_type: str = Field(..., pattern=r"^(email|sms|telegram)$")
    code: str = Field(..., min_length=1, max_length=255)


class ResendCodeRequest(BaseModel):
    channel_type: str = Field(..., pattern=r"^(email|sms|telegram)$")


class TelegramLinkResponse(BaseModel):
    deep_link: str
    expires_in: int
