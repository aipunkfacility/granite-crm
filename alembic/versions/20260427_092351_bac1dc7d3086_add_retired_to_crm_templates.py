"""add_retired_to_crm_templates

Revision ID: bac1dc7d3086
Revises: 7e6e2bbbc8b3
Create Date: 2026-04-27 09:23:51.019137

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bac1dc7d3086'
down_revision: Union[str, None] = '7e6e2bbbc8b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('crm_templates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('retired', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('crm_templates', schema=None) as batch_op:
        batch_op.drop_column('retired')
