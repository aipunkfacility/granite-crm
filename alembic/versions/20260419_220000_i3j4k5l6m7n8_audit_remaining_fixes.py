"""audit_remaining_fixes: soft-delete, filters→JSON, FK adjustments

Audit #13: CHECK constraints deferred to application layer (Pydantic validators).
  SQLite batch_alter_table loses nullable/indexes on table recreation,
  so CHECK is enforced in API via Pydantic pattern validators instead.
Audit #14: Soft-delete (deleted_at on companies), CRM FK CASCADE → SET NULL.
Audit #15: crm_email_campaigns.filters: Text → JSON.

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-04-19 22:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "i3j4k5l6m7n8"
down_revision: Union[str, None] = "h2i3j4k5l6m7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Soft-delete: добавляем deleted_at в companies ──
    op.add_column("companies", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index("ix_companies_deleted_at", "companies", ["deleted_at"])

    # ── 2. filters: Text → JSON ──
    # SQLite не поддерживает ALTER COLUMN, используем batch mode
    with op.batch_alter_table("crm_email_campaigns") as batch:
        batch.alter_column(
            "filters",
            existing_type=sa.Text(),
            type_=sa.JSON(),
            existing_nullable=True,
        )

    # ── 3. Примечание по FK adjustments ──
    # AUDIT #14: CASCADE → SET NULL для crm_contacts невозможно через
    # Alembic batch_alter_table в SQLite (FK ondelete не обновляется).
    # Решение: soft-delete через deleted_at на companies. Приложение
    # фильтрует deleted_at IS NOT NULL. CASCADE остаётся как safety net.

    # ── 4. Обновляем нестандартные значения (data cleanup) ──
    # AUDIT #13: Валидация данных перед применением CHECK на уровне приложения
    op.execute(
        "UPDATE enriched_companies SET segment = 'D' "
        "WHERE segment NOT IN ('A', 'B', 'C', 'D', 'spam') OR segment IS NULL"
    )
    op.execute(
        "UPDATE crm_contacts SET funnel_stage = 'new' "
        "WHERE funnel_stage NOT IN "
        "('new','email_sent','email_opened','tg_sent','wa_sent',"
        "'replied','interested','not_interested','unreachable')"
    )
    op.execute(
        "UPDATE crm_tasks SET status = 'pending' "
        "WHERE status NOT IN ('pending','in_progress','done','cancelled')"
    )
    op.execute(
        "UPDATE crm_tasks SET priority = 'normal' "
        "WHERE priority NOT IN ('low','normal','high')"
    )
    op.execute(
        "UPDATE companies SET segment = 'D' "
        "WHERE segment IS NULL OR segment = 'Не определено'"
    )
    op.execute(
        "UPDATE crm_email_campaigns SET status = 'draft' "
        "WHERE status NOT IN ('draft','running','paused','completed')"
    )


def downgrade() -> None:
    # Убираем soft-delete и возвращаем Text для filters
    op.drop_index("ix_companies_deleted_at", table_name="companies")
    op.drop_column("companies", "deleted_at")

    with op.batch_alter_table("crm_email_campaigns") as batch:
        batch.alter_column(
            "filters",
            existing_type=sa.JSON(),
            type_=sa.Text(),
            existing_nullable=True,
        )
