"""add_group_id_to_service_shares

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-19 19:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('service_shares', sa.Column('group_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_service_shares_group_id',
        'service_shares', 'service_groups',
        ['group_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_service_shares_group_id', 'service_shares', type_='foreignkey')
    op.drop_column('service_shares', 'group_id')
