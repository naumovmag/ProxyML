import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class ServiceGroupCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    sort_order: int = 0

class ServiceGroupUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    sort_order: int | None = None

class ServiceGroupRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ServiceBase(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    group_id: uuid.UUID | None = None
    service_type: str = Field(default="custom", max_length=50)
    base_url: str
    auth_type: str = Field(default="none")
    auth_token: str | None = None
    auth_header_name: str = "Authorization"
    default_model: str | None = None
    timeout_seconds: int = 120
    supports_streaming: bool = False
    extra_headers: dict | None = None
    health_check_path: str | None = None
    health_check_method: str = "GET"
    description: str | None = None
    tags: list[str] = []
    request_schema_hint: dict | None = None
    cache_enabled: bool = False
    cache_ttl_seconds: int = 86400
    is_active: bool = True

class ServiceCreate(ServiceBase):
    pass

class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    group_id: uuid.UUID | None = None
    service_type: str | None = None
    base_url: str | None = None
    auth_type: str | None = None
    auth_token: str | None = None
    auth_header_name: str | None = None
    default_model: str | None = None
    timeout_seconds: int | None = None
    supports_streaming: bool | None = None
    extra_headers: dict | None = None
    health_check_path: str | None = None
    health_check_method: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    request_schema_hint: dict | None = None
    cache_enabled: bool | None = None
    cache_ttl_seconds: int | None = None
    is_active: bool | None = None

class ServiceRead(ServiceBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class ServiceCatalogItem(BaseModel):
    slug: str
    name: str
    service_type: str
    description: str | None
    tags: list[str]
    supports_streaming: bool
    request_schema_hint: dict | None

    model_config = {"from_attributes": True}
