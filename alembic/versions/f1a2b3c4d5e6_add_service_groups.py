"""add service groups

Revision ID: f1a2b3c4d5e6
Revises: e9f3b2c6d7a8
Create Date: 2026-03-11

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP

revision: str = 'f1a2b3c4d5e6'
down_revision: str | None = 'e9f3b2c6d7a8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'service_groups',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), unique=True, nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column('services', sa.Column('group_id', UUID(as_uuid=True), nullable=True))
    op.create_index('ix_services_group_id', 'services', ['group_id'])
    op.create_foreign_key('fk_services_group_id', 'services', 'service_groups', ['group_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_services_group_id', 'services', type_='foreignkey')
    op.drop_index('ix_services_group_id', 'services')
    op.drop_column('services', 'group_id')
    op.drop_table('service_groups')
