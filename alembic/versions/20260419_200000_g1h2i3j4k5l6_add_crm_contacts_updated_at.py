"""add crm_contacts.updated_at

Revision ID: g1h2i3j4k5l6
Revises: f1a2b3c4d5e6
Create Date: 2026-04-19 20:00:00.000000

BUG-C3: crm_contacts.updated_at присутствует в ORM-модели (database.py),
но отсутствует во всех Alembic-миграциях. compare_metadata находит diff,
что приводит к падению test_no_diff_after_upgrade.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Проверяем, существует ли колонка (для idempotency)
    col_exists = conn.execute(text(
        "SELECT COUNT(*) FROM pragma_table_info('crm_contacts') WHERE name='updated_at'"
    )).scalar()

    if not col_exists:
        with op.batch_alter_table('crm_contacts', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('updated_at', sa.DateTime(), nullable=True)
            )

        # Backfill: заполняем updated_at из created_at для существующих записей
        conn.execute(text(
            "UPDATE crm_contacts SET updated_at = created_at WHERE updated_at IS NULL"
        ))


def downgrade() -> None:
    conn = op.get_bind()

    col_exists = conn.execute(text(
        "SELECT COUNT(*) FROM pragma_table_info('crm_contacts') WHERE name='updated_at'"
    )).scalar()

    if col_exists:
        with op.batch_alter_table('crm_contacts', schema=None) as batch_op:
            batch_op.drop_column('updated_at')
