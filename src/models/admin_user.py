import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from src.db.base import Base

class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now())
