"""fix_playground_timestamps_timezone

Revision ID: cc68f484ceed
Revises: bb57e373bddd
Create Date: 2026-03-17 11:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'cc68f484ceed'
down_revision: Union[str, None] = 'bb57e373bddd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.alter_column('playground_history', 'created_at',
                    type_=sa.TIMESTAMP(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_server_default=sa.text('now()'))
    op.alter_column('playground_presets', 'created_at',
                    type_=sa.TIMESTAMP(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_server_default=sa.text('now()'))
    op.alter_column('playground_presets', 'updated_at',
                    type_=sa.TIMESTAMP(timezone=True),
                    existing_type=sa.DateTime(),
                    existing_server_default=sa.text('now()'))

def downgrade() -> None:
    op.alter_column('playground_presets', 'updated_at',
                    type_=sa.DateTime(),
                    existing_type=sa.TIMESTAMP(timezone=True),
                    existing_server_default=sa.text('now()'))
    op.alter_column('playground_presets', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.TIMESTAMP(timezone=True),
                    existing_server_default=sa.text('now()'))
    op.alter_column('playground_history', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.TIMESTAMP(timezone=True),
                    existing_server_default=sa.text('now()'))
