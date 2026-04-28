"""hot_path_composite_indexes

Revision ID: l2g3h4i5j6k7
Revises: k1f2g3h4i5j6
Create Date: 2026-04-28 12:00:00.000000
"""
from collections.abc import Sequence

from alembic import op

revision: str = "l2g3h4i5j6k7"
down_revision: str | None = "k1f2g3h4i5j6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Composite indexes covering hot-path queries:
#   - request_logs: dashboard stats and /stats/recent
#   - api_keys:     listing + per-request validate
#   - service_shares: JOIN in list_accessible_services / check_service_access
#   - load_test_tasks: listing on LoadTestsPage
#
# CREATE INDEX CONCURRENTLY cannot run inside a transaction, so we COMMIT the
# alembic-managed transaction before issuing them. IF NOT EXISTS makes repeat
# `alembic upgrade head` runs (each pod start) a no-op.

_INDEXES: list[tuple[str, str]] = [
    ("ix_request_logs_owner_created",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_request_logs_owner_created "
     "ON request_logs (owner_id, created_at DESC)"),
    ("ix_request_logs_service_created",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_request_logs_service_created "
     "ON request_logs (service_id, created_at DESC)"),
    ("ix_request_logs_apikey_created",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_request_logs_apikey_created "
     "ON request_logs (api_key_id, created_at DESC) "
     "WHERE api_key_id IS NOT NULL"),
    ("ix_api_keys_owner_created",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_api_keys_owner_created "
     "ON api_keys (owner_id, created_at DESC)"),
    ("ix_api_keys_keyhash_active",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_api_keys_keyhash_active "
     "ON api_keys (key_hash, is_active)"),
    ("ix_service_shares_service_id",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_service_shares_service_id "
     "ON service_shares (service_id)"),
    ("ix_load_test_tasks_owner_created",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_load_test_tasks_owner_created "
     "ON load_test_tasks (owner_id, created_at DESC)"),
    ("ix_services_owner_active",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_services_owner_active "
     "ON services (owner_id, is_active)"),
]


def upgrade() -> None:
    op.execute("COMMIT")
    for _name, ddl in _INDEXES:
        op.execute(ddl)
    op.execute("ANALYZE request_logs")
    op.execute("ANALYZE api_keys")


def downgrade() -> None:
    op.execute("COMMIT")
    for name, _ddl in reversed(_INDEXES):
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
