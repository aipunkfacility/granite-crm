"""add updated_at to campaigns and rename call task_type

Revision ID: a1b2c3d4e5f6
Revises: b9fa3d4c7894
Create Date: 2026-04-18 12:00:00.000000

Two changes:
1. crm_tasks: rename task_type 'call' → 'other' (schema cleanup)
2. crm_email_campaigns: add updated_at column (nullable, backfill from created_at)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'b9fa3d4c7894'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- 1. task_type: call → other ---
    conn.execute(text(
        "UPDATE crm_tasks SET task_type = 'other' WHERE task_type = 'call'"
    ))

    # --- 2. updated_at для кампаний ---
    col_exists = conn.execute(text(
        "SELECT COUNT(*) FROM pragma_table_info('crm_email_campaigns') WHERE name='updated_at'"
    )).scalar()
    if not col_exists:
        with op.batch_alter_table('crm_email_campaigns', schema=None) as batch_op:
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))

    # Backfill: для существующих записей updated_at = created_at
    conn.execute(text(
        "UPDATE crm_email_campaigns SET updated_at = created_at "
        "WHERE updated_at IS NULL AND created_at IS NOT NULL"
    ))


def downgrade() -> None:
    conn = op.get_bind()

    # Убрать updated_at
    col_exists = conn.execute(text(
        "SELECT COUNT(*) FROM pragma_table_info('crm_email_campaigns') WHERE name='updated_at'"
    )).scalar()
    if col_exists:
        with op.batch_alter_table('crm_email_campaigns', schema=None) as batch_op:
            batch_op.drop_column('updated_at')

    # task_type 'call': нет обратной миграции данных (необратимо)
