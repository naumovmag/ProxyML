"""add_service_shares

Revision ID: c3d4e5f6a7b8
Revises: 25e63bbc508e
Create Date: 2026-03-19 18:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = '25e63bbc508e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'service_shares',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('service_id', UUID(as_uuid=True), sa.ForeignKey('services.id', ondelete='CASCADE'), nullable=False),
        sa.Column('shared_with_user_id', UUID(as_uuid=True), sa.ForeignKey('admin_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('shared_by_user_id', UUID(as_uuid=True), sa.ForeignKey('admin_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('service_id', 'shared_with_user_id', name='uq_service_shares_service_user'),
    )
    op.create_index('ix_service_shares_shared_with_user_id', 'service_shares', ['shared_with_user_id'])


def downgrade() -> None:
    op.drop_index('ix_service_shares_shared_with_user_id', table_name='service_shares')
    op.drop_table('service_shares')
