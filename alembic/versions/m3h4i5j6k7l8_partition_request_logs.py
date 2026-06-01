"""partition_request_logs

Convert request_logs into a RANGE-partitioned table (by created_at, daily),
keeping only the last N days of data. Drops the legacy table to release disk.

Revision ID: m3h4i5j6k7l8
Revises: l2g3h4i5j6k7
Create Date: 2026-05-28 00:00:00.000000
"""
from collections.abc import Sequence

from alembic import op

revision: str = "m3h4i5j6k7l8"
down_revision: str | None = "l2g3h4i5j6k7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RETENTION_DAYS = 7
AHEAD_DAYS = 3


def upgrade() -> None:
    # 1. Rename legacy table + its indexes (avoid name collisions with the new ones).
    op.execute("ALTER TABLE request_logs RENAME TO request_logs_legacy")
    op.execute("ALTER INDEX IF EXISTS request_logs_pkey RENAME TO request_logs_legacy_pkey")
    for idx in (
        "ix_request_logs_owner_id",
        "ix_request_logs_service_id",
        "ix_request_logs_service_slug",
        "ix_request_logs_created_at",
        "ix_request_logs_owner_created",
        "ix_request_logs_service_created",
        "ix_request_logs_apikey_created",
    ):
        op.execute(f"ALTER INDEX IF EXISTS {idx} RENAME TO {idx}_legacy")

    # 2. Create the new partitioned parent table (same columns as the model).
    op.execute(
        """
        CREATE TABLE request_logs (
            id UUID NOT NULL DEFAULT gen_random_uuid(),
            owner_id UUID,
            service_id UUID NOT NULL,
            service_slug VARCHAR(255) NOT NULL,
            api_key_id UUID,
            api_key_name VARCHAR(255),
            method VARCHAR(10) NOT NULL,
            path TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            request_size INTEGER NOT NULL DEFAULT 0,
            response_size INTEGER NOT NULL DEFAULT 0,
            duration_ms DOUBLE PRECISION NOT NULL,
            is_streaming BOOLEAN NOT NULL DEFAULT FALSE,
            is_cached BOOLEAN NOT NULL DEFAULT FALSE,
            is_fallback BOOLEAN NOT NULL DEFAULT FALSE,
            fallback_from_slug VARCHAR(255),
            error TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
        """
    )

    # 3. Indexes on the parent (auto-propagate to all current/future partitions).
    op.execute("CREATE INDEX ix_request_logs_owner_id ON request_logs (owner_id)")
    op.execute("CREATE INDEX ix_request_logs_service_id ON request_logs (service_id)")
    op.execute("CREATE INDEX ix_request_logs_service_slug ON request_logs (service_slug)")
    op.execute("CREATE INDEX ix_request_logs_created_at ON request_logs (created_at)")
    op.execute(
        "CREATE INDEX ix_request_logs_owner_created "
        "ON request_logs (owner_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_request_logs_service_created "
        "ON request_logs (service_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_request_logs_apikey_created "
        "ON request_logs (api_key_id, created_at DESC) "
        "WHERE api_key_id IS NOT NULL"
    )

    # 4. Create daily partitions: [today - RETENTION_DAYS, today + AHEAD_DAYS].
    op.execute(
        f"""
        DO $$
        DECLARE
            d DATE;
            partition_name TEXT;
            start_ts TEXT;
            end_ts TEXT;
        BEGIN
            FOR i IN -{RETENTION_DAYS}..{AHEAD_DAYS} LOOP
                d := (CURRENT_DATE + i);
                partition_name := 'request_logs_' || to_char(d, 'YYYYMMDD');
                start_ts := to_char(d, 'YYYY-MM-DD') || ' 00:00:00+00';
                end_ts := to_char(d + 1, 'YYYY-MM-DD') || ' 00:00:00+00';
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS %I PARTITION OF request_logs '
                    'FOR VALUES FROM (%L) TO (%L)',
                    partition_name, start_ts, end_ts
                );
            END LOOP;
        END $$
        """
    )

    # 5. Copy last N days of data from the legacy table.
    op.execute(
        f"""
        INSERT INTO request_logs (
            id, owner_id, service_id, service_slug, api_key_id, api_key_name,
            method, path, status_code, request_size, response_size, duration_ms,
            is_streaming, is_cached, is_fallback, fallback_from_slug, error, created_at
        )
        SELECT
            id, owner_id, service_id, service_slug, api_key_id, api_key_name,
            method, path, status_code, request_size, response_size, duration_ms,
            is_streaming, is_cached, is_fallback, fallback_from_slug, error, created_at
        FROM request_logs_legacy
        WHERE created_at >= NOW() - INTERVAL '{RETENTION_DAYS} days'
          AND created_at >= (CURRENT_DATE - {RETENTION_DAYS})::timestamptz
        """
    )

    # 6. Drop the legacy table — releases disk space immediately.
    op.execute("DROP TABLE request_logs_legacy CASCADE")

    op.execute("ANALYZE request_logs")


def downgrade() -> None:
    # Best-effort rollback: convert back to a non-partitioned table.
    # Any data older than current retention is irrecoverable.
    op.execute("ALTER TABLE request_logs RENAME TO request_logs_partitioned")
    op.execute(
        """
        CREATE TABLE request_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_id UUID,
            service_id UUID NOT NULL,
            service_slug VARCHAR(255) NOT NULL,
            api_key_id UUID,
            api_key_name VARCHAR(255),
            method VARCHAR(10) NOT NULL,
            path TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            request_size INTEGER NOT NULL DEFAULT 0,
            response_size INTEGER NOT NULL DEFAULT 0,
            duration_ms DOUBLE PRECISION NOT NULL,
            is_streaming BOOLEAN NOT NULL DEFAULT FALSE,
            is_cached BOOLEAN NOT NULL DEFAULT FALSE,
            is_fallback BOOLEAN NOT NULL DEFAULT FALSE,
            fallback_from_slug VARCHAR(255),
            error TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        INSERT INTO request_logs SELECT * FROM request_logs_partitioned
        """
    )
    op.execute("DROP TABLE request_logs_partitioned CASCADE")
    op.execute("CREATE INDEX ix_request_logs_owner_id ON request_logs (owner_id)")
    op.execute("CREATE INDEX ix_request_logs_service_id ON request_logs (service_id)")
    op.execute("CREATE INDEX ix_request_logs_service_slug ON request_logs (service_slug)")
    op.execute("CREATE INDEX ix_request_logs_created_at ON request_logs (created_at)")
