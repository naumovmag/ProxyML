import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class RegistrationField(BaseModel):
    name: str = Field(..., max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    type: str = Field(..., pattern=r"^(string|number|boolean|email|phone)$")
    required: bool = True
    unique: bool = False


class AuthSystemCreate(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    access_token_ttl_minutes: int = Field(default=60, ge=1, le=525600)
    refresh_token_ttl_days: int = Field(default=30, ge=1, le=365)
    registration_fields: list[RegistrationField] = []
    users_active_by_default: bool = True
    email_verification_enabled: bool = False
    require_email_verification: bool = False
    email_provider_type: str | None = None
    email_provider_config: dict | None = None
    email_from_address: str | None = None
    email_from_name: str | None = None
    verification_token_ttl_minutes: int = Field(default=1440, ge=5, le=10080)
    verification_redirect_url: str | None = None
    email_template_subject: str | None = None
    email_template_body: str | None = None

    @field_validator("registration_fields")
    @classmethod
    def validate_no_reserved_names(cls, v: list[RegistrationField]) -> list[RegistrationField]:
        reserved = {"email", "password", "id", "is_active", "created_at", "updated_at"}
        names = []
        for f in v:
            if f.name in reserved:
                raise ValueError(f"Field name '{f.name}' is reserved")
            if f.name in names:
                raise ValueError(f"Duplicate field name '{f.name}'")
            names.append(f.name)
        return v


class AuthSystemUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    access_token_ttl_minutes: int | None = Field(default=None, ge=1, le=525600)
    refresh_token_ttl_days: int | None = Field(default=None, ge=1, le=365)
    registration_fields: list[RegistrationField] | None = None
    users_active_by_default: bool | None = None
    email_verification_enabled: bool | None = None
    require_email_verification: bool | None = None
    email_provider_type: str | None = None
    email_provider_config: dict | None = None
    email_from_address: str | None = None
    email_from_name: str | None = None
    verification_token_ttl_minutes: int | None = Field(default=None, ge=5, le=10080)
    verification_redirect_url: str | None = None
    email_template_subject: str | None = None
    email_template_body: str | None = None
    is_active: bool | None = None


class AuthSystemRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    access_token_ttl_minutes: int
    refresh_token_ttl_days: int
    registration_fields: list[RegistrationField]
    users_active_by_default: bool
    email_verification_enabled: bool
    require_email_verification: bool
    email_provider_type: str | None
    email_provider_config: dict | None
    email_from_address: str | None
    email_from_name: str | None
    verification_token_ttl_minutes: int
    verification_redirect_url: str | None
    email_template_subject: str | None
    email_template_body: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Public auth schemas ---

class AuthRegisterRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6, max_length=255)
    fields: dict = {}


class AuthLoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=255)


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthRefreshRequest(BaseModel):
    refresh_token: str


class AuthUserRead(BaseModel):
    id: uuid.UUID
    email: str
    custom_fields: dict
    email_verified: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthUpdateProfileRequest(BaseModel):
    fields: dict = {}


class AuthChangePasswordRequest(BaseModel):
    old_password: str = Field(..., max_length=255)
    new_password: str = Field(..., min_length=6, max_length=255)


class AuthLogoutRequest(BaseModel):
    refresh_token: str


class AuthVerifyResponse(BaseModel):
    valid: bool
    user_id: str | None = None
    email: str | None = None
    email_verified: bool | None = None


class AdminUpdateAuthUser(BaseModel):
    email: str | None = Field(default=None, max_length=255)
    custom_fields: dict | None = None
    is_active: bool | None = None


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=255)
