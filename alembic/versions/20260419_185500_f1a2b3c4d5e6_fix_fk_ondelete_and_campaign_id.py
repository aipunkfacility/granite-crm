"""fix FK ondelete and add campaign_id FK

Revision ID: f1a2b3c4d5e6
Revises: e2f3a4b5c6d7
Create Date: 2026-04-19 18:55:00.000000

K6: raw_companies.merged_into — добавлен ON DELETE SET NULL.
     Ранее при удалении компании вызывалась ошибка FK constraint.

K7: crm_email_logs.campaign_id — добавлен FK на crm_email_campaigns(id)
     с ON DELETE SET NULL. Ранее campaign_id был plain Integer без FK —
     можно было ссылаться на несуществующую кампанию.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- K6: raw_companies.merged_into ON DELETE SET NULL ---
    # NOTE: "from" is a SQL reserved word — must quote it in raw SQL.
    fk_info = conn.execute(text(
        "SELECT * FROM pragma_foreign_key_list('raw_companies') "
        'WHERE "from"=\'merged_into\''
    )).fetchall()

    needs_fix = False
    if not fk_info:
        needs_fix = True
    else:
        # on_delete: 0=NONE, 1=CASCADE, 2=SET NULL, 3=SET DEFAULT, 4=RESTRICT
        on_delete_action = fk_info[0]["on_delete"] if isinstance(fk_info[0], dict) else None
        if isinstance(fk_info[0], tuple) and len(fk_info[0]) > 7:
            on_delete_action = fk_info[0][7]
        # В SQLite pragma_foreign_key_list on_delete — это элемент [7] в кортеже
        # или ключ 'on_delete' в dict. Нужна SET NULL (=2).
        try:
            row = fk_info[0]
            if isinstance(row, dict):
                on_delete_action = row.get("on_delete")
            else:
                on_delete_action = row[7] if len(row) > 7 else 0
        except (IndexError, KeyError):
            on_delete_action = 0

        if on_delete_action != 2:  # 2 = SET NULL
            needs_fix = True

    if needs_fix:
        conn.execute(text("""
            CREATE TABLE _raw_companies_tmp (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                source VARCHAR NOT NULL,
                source_url VARCHAR DEFAULT '',
                name VARCHAR NOT NULL,
                phones JSON DEFAULT '[]',
                address_raw TEXT DEFAULT '',
                website VARCHAR,
                emails JSON DEFAULT '[]',
                geo VARCHAR,
                messengers JSON DEFAULT '{}',
                scraped_at DATETIME,
                city VARCHAR NOT NULL,
                region VARCHAR NOT NULL DEFAULT '',
                merged_into INTEGER,
                FOREIGN KEY (merged_into) REFERENCES companies (id) ON DELETE SET NULL
            )
        """))
        conn.execute(text("""
            INSERT INTO _raw_companies_tmp
            SELECT id, source, source_url, name, phones, address_raw, website,
                   emails, geo, messengers, scraped_at, city, region, merged_into
            FROM raw_companies
        """))
        conn.execute(text("DROP TABLE raw_companies"))
        conn.execute(text("ALTER TABLE _raw_companies_tmp RENAME TO raw_companies"))
        # Восстанавливаем индексы
        conn.execute(text("CREATE INDEX ix_raw_companies_source ON raw_companies (source)"))
        conn.execute(text("CREATE INDEX ix_raw_companies_city ON raw_companies (city)"))
        conn.execute(text("CREATE INDEX ix_raw_companies_region ON raw_companies (region)"))

    # --- K7: crm_email_logs.campaign_id FK → crm_email_campaigns.id ---
    fk_exists = conn.execute(text(
        "SELECT COUNT(*) FROM pragma_foreign_key_list('crm_email_logs') "
        'WHERE "from"=\'campaign_id\''
    )).scalar()

    if not fk_exists:
        conn.execute(text("""
            CREATE TABLE _crm_email_logs_tmp (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                email_to VARCHAR NOT NULL,
                email_subject VARCHAR DEFAULT '',
                template_name VARCHAR DEFAULT '',
                campaign_id INTEGER,
                status VARCHAR DEFAULT 'pending',
                sent_at DATETIME,
                opened_at DATETIME,
                replied_at DATETIME,
                bounced_at DATETIME,
                error_message TEXT DEFAULT '',
                tracking_id VARCHAR,
                created_at DATETIME,
                FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE,
                FOREIGN KEY (campaign_id) REFERENCES crm_email_campaigns (id) ON DELETE SET NULL
            )
        """))
        conn.execute(text("""
            INSERT INTO _crm_email_logs_tmp
            SELECT id, company_id, email_to, email_subject, template_name,
                   campaign_id, status, sent_at, opened_at, replied_at,
                   bounced_at, error_message, tracking_id, created_at
            FROM crm_email_logs
        """))
        conn.execute(text("DROP TABLE crm_email_logs"))
        conn.execute(text("ALTER TABLE _crm_email_logs_tmp RENAME TO crm_email_logs"))
        # Восстанавливаем индексы
        conn.execute(text("CREATE INDEX ix_crm_email_logs_company_id ON crm_email_logs (company_id)"))
        conn.execute(text("CREATE INDEX ix_crm_email_logs_campaign_id ON crm_email_logs (campaign_id)"))
        conn.execute(text("CREATE INDEX ix_crm_email_logs_status ON crm_email_logs (status)"))
        conn.execute(text("CREATE UNIQUE INDEX ix_crm_email_logs_tracking_id ON crm_email_logs (tracking_id)"))


def downgrade() -> None:
    conn = op.get_bind()

    # Убрать FK с raw_companies.merged_into (возврат к plain FK без ON DELETE)
    # NOTE: "from" is a SQL reserved word — must quote it in raw SQL.
    fk_info = conn.execute(text(
        "SELECT * FROM pragma_foreign_key_list('raw_companies') "
        'WHERE "from"=\'merged_into\''
    )).fetchall()

    if fk_info:
        conn.execute(text("""
            CREATE TABLE _raw_companies_tmp (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                source VARCHAR NOT NULL,
                source_url VARCHAR DEFAULT '',
                name VARCHAR NOT NULL,
                phones JSON DEFAULT '[]',
                address_raw TEXT DEFAULT '',
                website VARCHAR,
                emails JSON DEFAULT '[]',
                geo VARCHAR,
                messengers JSON DEFAULT '{}',
                scraped_at DATETIME,
                city VARCHAR NOT NULL,
                region VARCHAR NOT NULL DEFAULT '',
                merged_into INTEGER,
                FOREIGN KEY (merged_into) REFERENCES companies (id)
            )
        """))
        conn.execute(text("""
            INSERT INTO _raw_companies_tmp
            SELECT id, source, source_url, name, phones, address_raw, website,
                   emails, geo, messengers, scraped_at, city, region, merged_into
            FROM raw_companies
        """))
        conn.execute(text("DROP TABLE raw_companies"))
        conn.execute(text("ALTER TABLE _raw_companies_tmp RENAME TO raw_companies"))
        conn.execute(text("CREATE INDEX ix_raw_companies_source ON raw_companies (source)"))
        conn.execute(text("CREATE INDEX ix_raw_companies_city ON raw_companies (city)"))
        conn.execute(text("CREATE INDEX ix_raw_companies_region ON raw_companies (region)"))

    # Убрать FK с crm_email_logs.campaign_id
    fk_exists = conn.execute(text(
        "SELECT COUNT(*) FROM pragma_foreign_key_list('crm_email_logs') "
        'WHERE "from"=\'campaign_id\''
    )).scalar()

    if fk_exists:
        conn.execute(text("""
            CREATE TABLE _crm_email_logs_tmp (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                email_to VARCHAR NOT NULL,
                email_subject VARCHAR DEFAULT '',
                template_name VARCHAR DEFAULT '',
                campaign_id INTEGER,
                status VARCHAR DEFAULT 'pending',
                sent_at DATETIME,
                opened_at DATETIME,
                replied_at DATETIME,
                bounced_at DATETIME,
                error_message TEXT DEFAULT '',
                tracking_id VARCHAR,
                created_at DATETIME,
                FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE
            )
        """))
        conn.execute(text("""
            INSERT INTO _crm_email_logs_tmp
            SELECT id, company_id, email_to, email_subject, template_name,
                   campaign_id, status, sent_at, opened_at, replied_at,
                   bounced_at, error_message, tracking_id, created_at
            FROM crm_email_logs
        """))
        conn.execute(text("DROP TABLE crm_email_logs"))
        conn.execute(text("ALTER TABLE _crm_email_logs_tmp RENAME TO crm_email_logs"))
        conn.execute(text("CREATE INDEX ix_crm_email_logs_company_id ON crm_email_logs (company_id)"))
        conn.execute(text("CREATE INDEX ix_crm_email_logs_campaign_id ON crm_email_logs (campaign_id)"))
        conn.execute(text("CREATE INDEX ix_crm_email_logs_status ON crm_email_logs (status)"))
        conn.execute(text("CREATE UNIQUE INDEX ix_crm_email_logs_tracking_id ON crm_email_logs (tracking_id)"))
