import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)
    email: str | None = None
    display_name: str | None = None


class UserRead(BaseModel):
    id: uuid.UUID
    username: str
    email: str | None
    display_name: str | None
    is_superadmin: bool
    is_approved: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
