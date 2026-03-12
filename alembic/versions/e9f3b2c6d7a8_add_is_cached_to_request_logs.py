"""add is_cached to request_logs

Revision ID: e9f3b2c6d7a8
Revises: d8e2a1b4c5f6
Create Date: 2026-03-11

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e9f3b2c6d7a8'
down_revision: str | None = 'd8e2a1b4c5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('request_logs', sa.Column('is_cached', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    op.drop_column('request_logs', 'is_cached')
