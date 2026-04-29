"""add rendered_body to crm_email_logs

Revision ID: d2e3f4a5b6c7
Revises: a5b6c7d8e9f0
Create Date: 2026-04-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, None] = 'a5b6c7d8e9f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Проверить, существует ли колонка в таблице (идемпотентность)."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)


def upgrade() -> None:
    """Добавить колонку rendered_body для хранения plain text отправленного письма."""
    if not _column_exists("crm_email_logs", "rendered_body"):
        with op.batch_alter_table('crm_email_logs', schema=None) as batch_op:
            batch_op.add_column(sa.Column('rendered_body', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('crm_email_logs', schema=None) as batch_op:
        batch_op.drop_column('rendered_body')
