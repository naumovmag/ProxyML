from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ModelRouteCreate(BaseModel):
    model_pattern: str
    target_service_id: UUID
    priority: int = 0
    override_model: str | None = None


class ModelRouteUpdate(BaseModel):
    model_pattern: str | None = None
    target_service_id: UUID | None = None
    priority: int | None = None
    override_model: str | None = None


class ModelRouteRead(BaseModel):
    id: UUID
    service_id: UUID
    model_pattern: str
    target_service_id: UUID
    target_service_name: str | None = None
    target_service_slug: str | None = None
    priority: int
    override_model: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
