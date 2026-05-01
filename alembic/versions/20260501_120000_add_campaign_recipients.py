"""add campaign_recipients table and recipient_mode column

Revision ID: 20260501_120000
Revises: 20260429_120000
Create Date: 2026-05-01 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3f4a5b6c7d8'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Добавить recipient_mode в crm_email_campaigns (server_default='filter' для обратной совместимости)
    op.add_column('crm_email_campaigns',
        sa.Column('recipient_mode', sa.String(10), server_default='filter', nullable=False))

    # 2. Создать junction-таблицу campaign_recipients
    op.create_table('campaign_recipients',
        sa.Column('campaign_id', sa.Integer,
                  sa.ForeignKey('crm_email_campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_id', sa.Integer,
                  sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        # ВАЖНО: нет server_default — консистентно с другими DateTime-колонками проекта
        # (все используют Python-side default=lambda, без server_default)
        sa.Column('added_at', sa.DateTime),
        sa.PrimaryKeyConstraint('campaign_id', 'company_id'),
    )

    # 3. Индекс по company_id для поиска «в каких кампаниях компания»
    op.create_index('ix_campaign_recipients_company', 'campaign_recipients', ['company_id'])


def downgrade():
    # Порядок важен: сначала зависимые объекты, потом колонка
    op.drop_index('ix_campaign_recipients_company')
    op.drop_table('campaign_recipients')
    op.drop_column('crm_email_campaigns', 'recipient_mode')
