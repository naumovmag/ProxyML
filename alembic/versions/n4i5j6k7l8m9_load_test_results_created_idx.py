"""load_test_results created_at index for retention cleanup

Revision ID: n4i5j6k7l8m9
Revises: m3h4i5j6k7l8
Create Date: 2026-06-11 12:00:00.000000
"""
from collections.abc import Sequence

from alembic import op

revision: str = "n4i5j6k7l8m9"
down_revision: str | None = "m3h4i5j6k7l8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Retention cleanup deletes load_test_results in chunks ordered by created_at;
# without this index every chunk is a sequential scan over the whole table.
# CREATE INDEX CONCURRENTLY cannot run inside a transaction, so COMMIT first
# (same pattern as l2g3h4i5j6k7_hot_path_composite_indexes).


def upgrade() -> None:
    op.execute("COMMIT")
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_load_test_results_created_at "
        "ON load_test_results (created_at)"
    )


def downgrade() -> None:
    op.execute("COMMIT")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_load_test_results_created_at")
