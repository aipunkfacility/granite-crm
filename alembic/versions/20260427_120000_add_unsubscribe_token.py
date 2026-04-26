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
    if not _column_exists("crm_contacts", "unsubscribe_token"):
        op.add_column(
            "crm_contacts",
            sa.Column("unsubscribe_token", sa.String, nullable=True, unique=True),
        )

    # Заполнить существующие записи уникальными токенами (идемпотентно)
    op.execute("""
        UPDATE crm_contacts
        SET unsubscribe_token = lower(hex(randomblob(16)))
        WHERE unsubscribe_token IS NULL
    """)

    if not _index_exists("crm_contacts", "ix_crm_contacts_unsubscribe_token"):
        op.create_index(
            "ix_crm_contacts_unsubscribe_token",
            "crm_contacts",
            ["unsubscribe_token"],
        )


def downgrade() -> None:
    op.drop_index("ix_crm_contacts_unsubscribe_token")
    op.drop_column("crm_contacts", "unsubscribe_token")
