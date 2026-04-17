"""add cities_ref unmatched_cities and region columns

Revision ID: b9fa3d4c7894
Revises: 025a08dcc789
Create Date: 2026-04-17 16:19:28.882301

Uses IF NOT EXISTS for tables (existing DBs created via create_all fallback).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'b9fa3d4c7894'
down_revision: Union[str, None] = '025a08dcc789'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- cities_ref: справочник городов из regions.yaml ---
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cities_ref (
            id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR NOT NULL,
            region VARCHAR NOT NULL,
            is_doppelganger BOOLEAN DEFAULT FALSE,
            is_populated BOOLEAN DEFAULT FALSE
        )
    """))
    conn.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_cities_ref_name ON cities_ref (name)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_cities_ref_region ON cities_ref (region)"
    ))

    # --- unmatched_cities: города, не найденные в справочнике ---
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS unmatched_cities (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            name VARCHAR NOT NULL,
            detected_from VARCHAR NOT NULL DEFAULT '',
            context TEXT NOT NULL DEFAULT '',
            created_at DATETIME,
            resolved BOOLEAN DEFAULT FALSE,
            resolved_to VARCHAR
        )
    """))
    conn.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_unmatched_cities_name ON unmatched_cities (name)"
    ))

    # --- region column on companies ---
    # Check if column already exists (for existing DBs)
    col_exists = conn.execute(text(
        "SELECT COUNT(*) FROM pragma_table_info('companies') WHERE name='region'"
    )).scalar()
    if not col_exists:
        with op.batch_alter_table('companies', schema=None) as batch_op:
            batch_op.add_column(sa.Column('region', sa.String(), nullable=False, server_default=''))
            batch_op.create_index(batch_op.f('ix_companies_region'), ['region'], unique=False)

    # --- region column on raw_companies ---
    col_exists = conn.execute(text(
        "SELECT COUNT(*) FROM pragma_table_info('raw_companies') WHERE name='region'"
    )).scalar()
    if not col_exists:
        with op.batch_alter_table('raw_companies', schema=None) as batch_op:
            batch_op.add_column(sa.Column('region', sa.String(), nullable=False, server_default=''))
            batch_op.create_index(batch_op.f('ix_raw_companies_region'), ['region'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()

    # Check columns exist before dropping
    col_exists = conn.execute(text(
        "SELECT COUNT(*) FROM pragma_table_info('raw_companies') WHERE name='region'"
    )).scalar()
    if col_exists:
        with op.batch_alter_table('raw_companies', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_raw_companies_region'))
            batch_op.drop_column('region')

    col_exists = conn.execute(text(
        "SELECT COUNT(*) FROM pragma_table_info('companies') WHERE name='region'"
    )).scalar()
    if col_exists:
        with op.batch_alter_table('companies', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_companies_region'))
            batch_op.drop_column('region')

    conn.execute(text("DROP TABLE IF EXISTS unmatched_cities"))
    conn.execute(text("DROP INDEX IF EXISTS ix_cities_ref_region"))
    conn.execute(text("DROP INDEX IF EXISTS ix_cities_ref_name"))
    conn.execute(text("DROP TABLE IF EXISTS cities_ref"))
