from datetime import datetime
from pydantic import BaseModel


class SystemSettingsRead(BaseModel):
    ai_enabled: bool
    llm_service_slug: str | None
    llm_model: str | None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SystemSettingsUpdate(BaseModel):
    ai_enabled: bool | None = None
    llm_service_slug: str | None = None
    llm_model: str | None = None
