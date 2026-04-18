"""add region to enriched_companies and composite index for follow-up

Revision ID: e2f3a4b5c6d7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-18 20:00:00.000000

Two changes:
1. ARCH-1: enriched_companies — add region column (backfill from companies)
2. ARCH-4: crm_contacts — composite index (funnel_stage, stop_automation)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- 1. ARCH-1: region для enriched_companies ---
    col_exists = conn.execute(text(
        "SELECT COUNT(*) FROM pragma_table_info('enriched_companies') WHERE name='region'"
    )).scalar()
    if not col_exists:
        with op.batch_alter_table('enriched_companies', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('region', sa.String(), nullable=False, server_default='')
            )
        # Создаём индекс отдельно, чтобы batch_alter_table не путался
        idx_region = conn.execute(text(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='index' AND name='ix_enriched_companies_region'"
        )).scalar()
        if not idx_region:
            op.create_index(
                'ix_enriched_companies_region', 'enriched_companies', ['region']
            )

    # Backfill: region из companies для существующих записей
    conn.execute(text(
        "UPDATE enriched_companies SET region = "
        "(SELECT region FROM companies WHERE companies.id = enriched_companies.id) "
        "WHERE region = '' OR region IS NULL"
    ))

    # --- 2. ARCH-4: составной индекс для follow-up запроса ---
    idx_exists = conn.execute(text(
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE type='index' AND name='ix_crm_contacts_funnel_stop'"
    )).scalar()
    if not idx_exists:
        op.create_index(
            'ix_crm_contacts_funnel_stop',
            'crm_contacts',
            ['funnel_stage', 'stop_automation'],
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Убрать составной индекс (простый drop, не batch_alter_table)
    idx_exists = conn.execute(text(
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE type='index' AND name='ix_crm_contacts_funnel_stop'"
    )).scalar()
    if idx_exists:
        op.drop_index('ix_crm_contacts_funnel_stop', table_name='crm_contacts')

    # Убрать region из enriched_companies через raw SQL.
    # batch_alter_table НЕ подходит: ORM-модель уже содержит region + index=True,
    # и batch_alter_table при пересоздании таблицы пытается создать индекс
    # по колонке, которую мы удаляем. Raw SQL — надёжный вариант для SQLite.
    col_exists = conn.execute(text(
        "SELECT COUNT(*) FROM pragma_table_info('enriched_companies') WHERE name='region'"
    )).scalar()
    if col_exists:
        # Убираем индекс сначала
        idx_region = conn.execute(text(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='index' AND name='ix_enriched_companies_region'"
        )).scalar()
        if idx_region:
            op.drop_index('ix_enriched_companies_region', table_name='enriched_companies')

        # Пересоздаём таблицу без region через raw SQL (SQLite не поддерживает DROP COLUMN < 3.35)
        conn.execute(text("""
            CREATE TABLE _enriched_companies_tmp (
                id INTEGER NOT NULL PRIMARY KEY,
                name VARCHAR NOT NULL,
                phones JSON,
                address_raw TEXT DEFAULT '',
                website VARCHAR,
                emails JSON,
                city VARCHAR NOT NULL,
                messengers JSON DEFAULT '{}',
                tg_trust JSON DEFAULT '{}',
                cms VARCHAR DEFAULT 'unknown',
                has_marquiz BOOLEAN DEFAULT 0,
                is_network BOOLEAN DEFAULT 0,
                crm_score INTEGER DEFAULT 0,
                segment VARCHAR DEFAULT 'D',
                updated_at DATETIME,
                FOREIGN KEY (id) REFERENCES companies (id) ON DELETE CASCADE
            )
        """))
        conn.execute(text("""
            INSERT INTO _enriched_companies_tmp (
                id, name, phones, address_raw, website, emails, city,
                messengers, tg_trust, cms, has_marquiz, is_network,
                crm_score, segment, updated_at
            ) SELECT
                id, name, phones, address_raw, website, emails, city,
                messengers, tg_trust, cms, has_marquiz, is_network,
                crm_score, segment, updated_at
            FROM enriched_companies
        """))
        conn.execute(text("DROP TABLE enriched_companies"))
        conn.execute(text("ALTER TABLE _enriched_companies_tmp RENAME TO enriched_companies"))

        # Пересоздаём индексы enriched_companies
        conn.execute(text(
            "CREATE INDEX ix_enriched_companies_city ON enriched_companies (city)"
        ))
        conn.execute(text(
            "CREATE INDEX ix_enriched_companies_crm_score ON enriched_companies (crm_score)"
        ))
        conn.execute(text(
            "CREATE INDEX ix_enriched_companies_segment ON enriched_companies (segment)"
        ))
