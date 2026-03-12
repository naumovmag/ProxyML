import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class ApiKeyCreate(BaseModel):
    name: str = Field(..., max_length=255)
    allowed_services: list[str] | None = None
    rate_limit_rpm: int | None = None
    expires_at: datetime | None = None

class ApiKeyRead(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    allowed_services: list[str] | None
    rate_limit_rpm: int | None
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}

class ApiKeyCreated(ApiKeyRead):
    raw_key: str  # shown once at creation
