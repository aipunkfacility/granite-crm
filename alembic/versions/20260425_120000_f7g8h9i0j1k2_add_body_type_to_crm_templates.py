"""add body_type to crm_templates

Revision ID: f7g8h9i0j1k2
Revises: 20260425_120000_add_sources
Create Date: 2026-04-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7g8h9i0j1k2'
down_revision: Union[str, None] = '20260425_120000_add_sources'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'crm_templates',
        sa.Column('body_type', sa.String(10), server_default='plain', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('crm_templates', 'body_type')
