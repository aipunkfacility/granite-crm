"""add_merged_into_to_companies: FK column for company merge tracking

Phase 3.4: Added merged_into column to companies table.
When a company is merged into another, this column records the target ID.
ON DELETE SET NULL ensures the FK is cleaned if the target is deleted.

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-04-19 23:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "j4k5l6m7n8o9"
down_revision: Union[str, None] = "i3j4k5l6m7n8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("merged_into", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_companies_merged_into", "companies", ["merged_into"],
    )
    # FK: SET NULL при удалении target-компании
    # SQLite batch mode для FK
    with op.batch_alter_table("companies") as batch:
        batch.create_foreign_key(
            "fk_companies_merged_into",
            referent_table="companies",
            local_cols=["merged_into"],
            remote_cols=["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("companies") as batch:
        batch.drop_constraint("fk_companies_merged_into", type_="foreignkey")
    op.drop_index("ix_companies_merged_into", table_name="companies")
    op.drop_column("companies", "merged_into")
