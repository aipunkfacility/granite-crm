"""add_total_recipients_to_campaigns

Revision ID: a5b6c7d8e9f0
Revises: 7e6e2bbbc8b3
Create Date: 2026-04-27 14:00:00.000000

FIX-A5: Добавлена колонка total_recipients в crm_email_campaigns.
Хранит количество получателей на момент старта кампании,
чтобы SSE progress не пересчитывал _get_campaign_recipients() при каждом реконнекте.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5b6c7d8e9f0'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('crm_email_campaigns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('total_recipients', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('crm_email_campaigns', schema=None) as batch_op:
        batch_op.drop_column('total_recipients')
