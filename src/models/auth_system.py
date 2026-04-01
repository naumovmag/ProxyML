import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from src.db.base import Base


class AuthSystem(Base):
    __tablename__ = "auth_systems"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    access_token_ttl_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    refresh_token_ttl_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    registration_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    jwt_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    users_active_by_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_verification_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    require_email_verification: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_provider_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email_provider_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    email_from_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_token_ttl_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    verification_redirect_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email_template_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email_template_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc))
