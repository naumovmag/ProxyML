import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PermissionCreate(BaseModel):
    slug: str = Field(..., max_length=100, pattern=r"^[a-z][a-z0-9_.]*$")
    name: str = Field(..., max_length=255)
    description: str | None = None


class PermissionUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None


class PermissionRead(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    slug: str = Field(..., max_length=100, pattern=r"^[a-z][a-z0-9_-]*$")
    name: str = Field(..., max_length=255)
    description: str | None = None
    is_default: bool = False
    is_admin_role: bool = False
    permission_ids: list[uuid.UUID] = []


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    is_default: bool | None = None
    is_admin_role: bool | None = None


class RoleRead(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    is_default: bool
    is_system: bool
    is_admin_role: bool
    permissions: list[PermissionRead] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserRolesAssign(BaseModel):
    role_ids: list[uuid.UUID]


class UserRoleAdd(BaseModel):
    role_id: uuid.UUID


class RolePermissionsSet(BaseModel):
    permission_ids: list[uuid.UUID]
