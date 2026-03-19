import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Float, Integer, ForeignKey, Index, func, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from src.db.base import Base, UUIDMixin, TimestampMixin


class LoadTestTask(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "load_test_tasks"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    service_type: Mapped[str] = mapped_column(String(50), nullable=False)
    test_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    test_method: Mapped[str] = mapped_column(String(10), nullable=False, default="POST")
    test_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    test_headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="stopped")
    max_runs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_load_test_tasks_owner_id", "owner_id"),
        Index("ix_load_test_tasks_service_id", "service_id"),
    )


class LoadTestResult(Base, UUIDMixin):
    __tablename__ = "load_test_results"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("load_test_tasks.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    request_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_load_test_results_task_created", "task_id", "created_at"),
    )
