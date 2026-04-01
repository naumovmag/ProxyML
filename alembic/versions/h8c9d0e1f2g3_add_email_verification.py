"""add_email_verification

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-04-01 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP

revision: str = "h8c9d0e1f2g3"
down_revision: Union[str, None] = "g7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Auth systems — email verification config
    op.add_column("auth_systems", sa.Column("email_verification_enabled", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("auth_systems", sa.Column("require_email_verification", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("auth_systems", sa.Column("email_provider_type", sa.String(50), nullable=True))
    op.add_column("auth_systems", sa.Column("email_provider_config", JSONB, nullable=True))
    op.add_column("auth_systems", sa.Column("email_from_address", sa.String(255), nullable=True))
    op.add_column("auth_systems", sa.Column("email_from_name", sa.String(255), nullable=True))
    op.add_column("auth_systems", sa.Column("verification_token_ttl_minutes", sa.Integer, nullable=False, server_default="1440"))
    op.add_column("auth_systems", sa.Column("verification_redirect_url", sa.String(500), nullable=True))
    op.add_column("auth_systems", sa.Column("email_template_subject", sa.String(500), nullable=True))
    op.add_column("auth_systems", sa.Column("email_template_body", sa.Text, nullable=True))

    # Auth users — email verified flag
    op.add_column("auth_users", sa.Column("email_verified", sa.Boolean, nullable=False, server_default="false"))

    # Email verification tokens table
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("auth_user_id", UUID(as_uuid=True), sa.ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("email_verification_tokens")
    op.drop_column("auth_users", "email_verified")
    op.drop_column("auth_systems", "email_template_body")
    op.drop_column("auth_systems", "email_template_subject")
    op.drop_column("auth_systems", "verification_redirect_url")
    op.drop_column("auth_systems", "verification_token_ttl_minutes")
    op.drop_column("auth_systems", "email_from_name")
    op.drop_column("auth_systems", "email_from_address")
    op.drop_column("auth_systems", "email_provider_config")
    op.drop_column("auth_systems", "email_provider_type")
    op.drop_column("auth_systems", "require_email_verification")
    op.drop_column("auth_systems", "email_verification_enabled")
