"""add suspicious_open flag to email logs

Revision ID: 8c23ebd8d935
Revises: e3f4a5b6c7d8
Create Date: 2026-05-31 01:58:33.788167
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8c23ebd8d935'
down_revision: Union[str, None] = 'e3f4a5b6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('crm_email_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('suspicious_open', sa.Boolean(), server_default='0', nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('crm_email_logs', schema=None) as batch_op:
        batch_op.drop_column('suspicious_open')
