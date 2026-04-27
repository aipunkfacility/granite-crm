"""add unsubscribe_token to crm_contacts

Revision ID: add_unsubscribe_token
Revises: be707cef6260
Create Date: 2026-04-27 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_unsubscribe_token"
down_revision = "be707cef6260"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)


def _index_exists(table: str, index_name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(sa.text(f"PRAGMA index_list({table})"))
    return any(row[1] == index_name for row in result)


def upgrade() -> None:
    # FIX-1: Используем batch_alter_table для SQLite-совместимости.
    # op.add_column с unique=True вызывает ALTER TABLE ADD CONSTRAINT UNIQUE,
    # что SQLite не поддерживает. Добавляем колонку без unique,
    # затем создаём UNIQUE-индекс отдельно.
    if not _column_exists("crm_contacts", "unsubscribe_token"):
        with op.batch_alter_table("crm_contacts", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("unsubscribe_token", sa.String, nullable=True),
            )

    # Заполнить существующие записи уникальными токенами (идемпотентно)
    op.execute("""
        UPDATE crm_contacts
        SET unsubscribe_token = lower(hex(randomblob(16)))
        WHERE unsubscribe_token IS NULL
    """)

    # Сделать колонку NOT NULL (после заполнения всех записей)
    with op.batch_alter_table("crm_contacts", schema=None) as batch_op:
        batch_op.alter_column(
            "unsubscribe_token",
            nullable=False,
            existing_type=sa.String(),
            existing_server_default=None,
        )

    # Создаём UNIQUE-индекс отдельно (поддерживается SQLite)
    if not _index_exists("crm_contacts", "ix_crm_contacts_unsubscribe_token"):
        op.create_index(
            "ix_crm_contacts_unsubscribe_token",
            "crm_contacts",
            ["unsubscribe_token"],
            unique=True,
        )


def downgrade() -> None:
    # FIX-1: Используем batch_alter_table для drop_column в SQLite
    op.drop_index("ix_crm_contacts_unsubscribe_token")
    with op.batch_alter_table("crm_contacts", schema=None) as batch_op:
        batch_op.drop_column("unsubscribe_token")
