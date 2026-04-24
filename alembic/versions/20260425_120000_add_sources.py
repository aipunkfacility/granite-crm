"""add sources column to companies

Revision ID: 20260425_120000_add_sources
Revises: 5e366843be2f
Create Date: 2026-04-25 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '20260425_120000_add_sources'
down_revision = '5e366843be2f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('sources', sa.JSON(), nullable=True, server_default='[]'))


def downgrade() -> None:
    op.drop_column('companies', 'sources')
