"""add description to crm_templates

Revision ID: c1d2e3f4a5b6
Revises: bac1dc7d3086
Create Date: 2026-04-27 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'bac1dc7d3086'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Проверить, существует ли колонка в таблице (идемпотентность)."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)


def upgrade() -> None:
    # FIX-2: Миграция для description, которая отсутствовала в Phase 2.
    # Колонка была добавлена в ORM (database.py:302), но без Alembic-миграции.
    # Идемпотентная проверка: пропускаем если колонка уже существует
    # (например, при create_all() fallback).
    if not _column_exists("crm_templates", "description"):
        with op.batch_alter_table('crm_templates', schema=None) as batch_op:
            batch_op.add_column(sa.Column('description', sa.String(), server_default='', nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('crm_templates', schema=None) as batch_op:
        batch_op.drop_column('description')
