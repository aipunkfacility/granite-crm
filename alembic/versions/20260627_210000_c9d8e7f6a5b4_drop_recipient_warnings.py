"""drop recipient_warnings column

Revision ID: c9d8e7f6a5b4
Revises: b96330ccd21a
Create Date: 2026-06-27 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d8e7f6a5b4'
down_revision: Union[str, None] = 'b96330ccd21a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('crm_email_campaigns', schema=None) as batch_op:
        batch_op.drop_column('recipient_warnings')


def downgrade() -> None:
    with op.batch_alter_table('crm_email_campaigns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('recipient_warnings', sa.JSON(), nullable=True))
