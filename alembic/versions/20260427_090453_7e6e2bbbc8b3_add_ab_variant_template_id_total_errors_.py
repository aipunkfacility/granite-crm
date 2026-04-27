"""add_ab_variant_template_id_total_errors_to_logs

Revision ID: 7e6e2bbbc8b3
Revises: add_unsubscribe_token
Create Date: 2026-04-27 09:04:53.999193

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e6e2bbbc8b3'
down_revision: Union[str, None] = 'add_unsubscribe_token'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FIX-1: Убрана дублирующая логика с unsubscribe_token.
    # Предыдущая миграция (add_unsubscribe_token) теперь сама создаёт
    # колонку, заполняет токены и создаёт UNIQUE-индекс.
    # Здесь только добавляем ab_variant, template_id, total_errors.

    # 1. crm_email_campaigns: добавить total_errors
    with op.batch_alter_table('crm_email_campaigns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('total_errors', sa.Integer(), nullable=True))

    # 2. crm_email_logs: добавить ab_variant и template_id
    with op.batch_alter_table('crm_email_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ab_variant', sa.String(length=1), nullable=True))
        batch_op.add_column(sa.Column('template_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_email_logs_template_id', 'crm_templates', ['template_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('crm_email_logs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_email_logs_template_id', type_='foreignkey')
        batch_op.drop_column('template_id')
        batch_op.drop_column('ab_variant')

    with op.batch_alter_table('crm_email_campaigns', schema=None) as batch_op:
        batch_op.drop_column('total_errors')
