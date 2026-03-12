"""add cache fields to services

Revision ID: d8e2a1b4c5f6
Revises: ac5f99c3f7b3
Create Date: 2026-03-11

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd8e2a1b4c5f6'
down_revision: str | None = 'ac5f99c3f7b3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('services', sa.Column('cache_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('services', sa.Column('cache_ttl_seconds', sa.Integer(), nullable=False, server_default=sa.text('86400')))


def downgrade() -> None:
    op.drop_column('services', 'cache_ttl_seconds')
    op.drop_column('services', 'cache_enabled')
