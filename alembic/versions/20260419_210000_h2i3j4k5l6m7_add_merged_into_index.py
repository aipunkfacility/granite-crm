"""add index on raw_companies.merged_into

FIX AUDIT-3 #14: FK column raw_companies.merged_into had no index.
SQLite does NOT auto-create indexes for FK columns, causing full table scans
on any query that JOINs or filters by merged_into.

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-04-19 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'h2i3j4k5l6m7'
down_revision: Union[str, None] = 'g1h2i3j4k5l6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_raw_companies_merged_into',
        'raw_companies',
        ['merged_into'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_raw_companies_merged_into', table_name='raw_companies')
