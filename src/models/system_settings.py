from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import TIMESTAMP
from src.db.base import Base


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    llm_service_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )
