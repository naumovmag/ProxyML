"""add multi tenancy

Revision ID: a2b3c4d5e6f7
Revises: 1c5d46a54a51
Create Date: 2026-03-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = '1c5d46a54a51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- admin_users: add new columns ---
    op.add_column('admin_users', sa.Column('email', sa.String(255), nullable=True))
    op.add_column('admin_users', sa.Column('display_name', sa.String(255), nullable=True))
    op.add_column('admin_users', sa.Column('is_superadmin', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('admin_users', sa.Column('is_approved', sa.Boolean(), nullable=False, server_default='false'))

    # --- Add owner_id to services ---
    op.add_column('services', sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_services_owner', 'services', 'admin_users', ['owner_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_services_owner_id', 'services', ['owner_id'])

    # --- Add owner_id to service_groups ---
    op.add_column('service_groups', sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_service_groups_owner', 'service_groups', 'admin_users', ['owner_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_service_groups_owner_id', 'service_groups', ['owner_id'])

    # --- Add owner_id to api_keys ---
    op.add_column('api_keys', sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_api_keys_owner', 'api_keys', 'admin_users', ['owner_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_api_keys_owner_id', 'api_keys', ['owner_id'])

    # --- Add owner_id to request_logs (no FK for performance) ---
    op.add_column('request_logs', sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_request_logs_owner_id', 'request_logs', ['owner_id'])

    # --- Drop global unique on names (allow same name per different owners) ---
    op.drop_constraint('services_name_key', 'services', type_='unique')
    op.drop_constraint('service_groups_name_key', 'service_groups', type_='unique')


def downgrade() -> None:
    # Restore unique constraints on names
    op.create_unique_constraint('service_groups_name_key', 'service_groups', ['name'])
    op.create_unique_constraint('services_name_key', 'services', ['name'])

    # Drop owner_id from request_logs
    op.drop_index('ix_request_logs_owner_id', table_name='request_logs')
    op.drop_column('request_logs', 'owner_id')

    # Drop owner_id from api_keys
    op.drop_index('ix_api_keys_owner_id', table_name='api_keys')
    op.drop_constraint('fk_api_keys_owner', 'api_keys', type_='foreignkey')
    op.drop_column('api_keys', 'owner_id')

    # Drop owner_id from service_groups
    op.drop_index('ix_service_groups_owner_id', table_name='service_groups')
    op.drop_constraint('fk_service_groups_owner', 'service_groups', type_='foreignkey')
    op.drop_column('service_groups', 'owner_id')

    # Drop owner_id from services
    op.drop_index('ix_services_owner_id', table_name='services')
    op.drop_constraint('fk_services_owner', 'services', type_='foreignkey')
    op.drop_column('services', 'owner_id')

    # Drop new columns from admin_users
    op.drop_column('admin_users', 'is_approved')
    op.drop_column('admin_users', 'is_superadmin')
    op.drop_column('admin_users', 'display_name')
    op.drop_column('admin_users', 'email')
