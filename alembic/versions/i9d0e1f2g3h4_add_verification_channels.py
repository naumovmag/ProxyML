"""add_verification_channels

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-04-01 14:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP

revision: str = "i9d0e1f2g3h4"
down_revision: Union[str, None] = "h8c9d0e1f2g3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create verification_channels table
    op.create_table(
        "verification_channels",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("auth_system_id", UUID(as_uuid=True), sa.ForeignKey("auth_systems.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("channel_type", sa.String(50), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("provider_config", JSONB, nullable=False, server_default="{}"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("settings", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("auth_system_id", "channel_type", name="uq_verification_channels_system_type"),
    )

    # 2. Create verification_codes table
    op.create_table(
        "verification_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("auth_user_id", UUID(as_uuid=True), sa.ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("channel_id", UUID(as_uuid=True), sa.ForeignKey("verification_channels.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("code_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 3. Add phone/telegram fields to auth_users
    op.add_column("auth_users", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("auth_users", sa.Column("phone_verified", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("auth_users", sa.Column("telegram_chat_id", sa.String(50), nullable=True))
    op.add_column("auth_users", sa.Column("telegram_verified", sa.Boolean, nullable=False, server_default="false"))

    # 4a. Partial unique index for phone
    op.execute(
        sa.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_auth_users_system_phone ON auth_users (auth_system_id, phone) WHERE phone IS NOT NULL")
    )

    # 4. Data migration: copy existing email provider configs into verification_channels
    op.execute(sa.text("""
        INSERT INTO verification_channels (id, auth_system_id, channel_type, provider_type, provider_config, is_enabled, is_required, priority, settings, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            id,
            'email',
            email_provider_type,
            COALESCE(email_provider_config, '{}'),
            email_verification_enabled,
            require_email_verification,
            0,
            jsonb_build_object(
                'from_address', COALESCE(email_from_address, ''),
                'from_name', COALESCE(email_from_name, ''),
                'verification_mode', 'link',
                'code_ttl_minutes', verification_token_ttl_minutes,
                'redirect_url', COALESCE(verification_redirect_url, ''),
                'template_subject', COALESCE(email_template_subject, ''),
                'template_body', COALESCE(email_template_body, '')
            ),
            NOW(),
            NOW()
        FROM auth_systems
        WHERE email_provider_type IS NOT NULL
    """))

    # 5. Migrate email_verification_tokens → verification_codes
    op.execute(sa.text("""
        INSERT INTO verification_codes (id, auth_user_id, channel_id, code_hash, expires_at, created_at)
        SELECT
            evt.id,
            evt.auth_user_id,
            vc.id,
            evt.token_hash,
            evt.expires_at,
            evt.created_at
        FROM email_verification_tokens evt
        JOIN auth_users au ON au.id = evt.auth_user_id
        JOIN verification_channels vc ON vc.auth_system_id = au.auth_system_id AND vc.channel_type = 'email'
        ON CONFLICT (code_hash) DO NOTHING
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_auth_users_system_phone"))
    op.drop_table("verification_codes")
    op.drop_column("auth_users", "telegram_verified")
    op.drop_column("auth_users", "telegram_chat_id")
    op.drop_column("auth_users", "phone_verified")
    op.drop_column("auth_users", "phone")
    op.drop_table("verification_channels")
