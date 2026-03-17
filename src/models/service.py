import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from src.db.base import Base

class Service(Base):
    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=True, index=True)
    group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("service_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    service_type: Mapped[str] = mapped_column(String(50), nullable=False, default="custom")
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    auth_type: Mapped[str] = mapped_column(String(50), nullable=False, default="none")
    auth_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_header_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Authorization")
    default_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    supports_streaming: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extra_headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    health_check_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    health_check_method: Mapped[str] = mapped_column(String(10), nullable=False, default="GET")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    request_schema_hint: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cache_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cache_ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=86400)
    fallback_service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id", ondelete="SET NULL"), nullable=True)
    fallback_on_statuses: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=lambda: [502, 503, 504])
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc))
