"""add_service_id_to_playground_presets

Revision ID: 862ce616503d
Revises: cc68f484ceed
Create Date: 2026-03-17 14:05:46.217071
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '862ce616503d'
down_revision: Union[str, None] = 'cc68f484ceed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('playground_presets', sa.Column('service_id', sa.UUID(), nullable=True))
    op.create_index('ix_playground_presets_service_id', 'playground_presets', ['service_id'], unique=False)
    op.create_foreign_key('fk_playground_presets_service_id', 'playground_presets', 'services', ['service_id'], ['id'], ondelete='CASCADE')

def downgrade() -> None:
    op.drop_constraint('fk_playground_presets_service_id', 'playground_presets', type_='foreignkey')
    op.drop_index('ix_playground_presets_service_id', table_name='playground_presets')
    op.drop_column('playground_presets', 'service_id')
