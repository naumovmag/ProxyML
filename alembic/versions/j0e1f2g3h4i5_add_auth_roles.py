"""add_auth_roles

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-04-17 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

revision: str = "j0e1f2g3h4i5"
down_revision: str | None = "faffbc5522fc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create auth_permissions table
    op.create_table(
        "auth_permissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("auth_system_id", UUID(as_uuid=True), sa.ForeignKey("auth_systems.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("auth_system_id", "slug", name="uq_auth_permissions_system_slug"),
    )

    # 2. Create auth_roles table
    op.create_table(
        "auth_roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("auth_system_id", UUID(as_uuid=True), sa.ForeignKey("auth_systems.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("auth_system_id", "slug", name="uq_auth_roles_system_slug"),
    )

    # 3. Create auth_role_permissions bridge table
    op.create_table(
        "auth_role_permissions",
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("auth_roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", UUID(as_uuid=True), sa.ForeignKey("auth_permissions.id", ondelete="CASCADE"), primary_key=True),
    )

    # 4. Create auth_user_roles bridge table
    op.create_table(
        "auth_user_roles",
        sa.Column("auth_user_id", UUID(as_uuid=True), sa.ForeignKey("auth_users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("auth_roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("assigned_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("assigned_by", UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("auth_user_roles")
    op.drop_table("auth_role_permissions")
    op.drop_table("auth_roles")
    op.drop_table("auth_permissions")
