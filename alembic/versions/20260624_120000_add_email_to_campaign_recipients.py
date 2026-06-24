"""add email to campaign_recipients PK

Expands each existing row into N rows — one per active company email.

Revision ID: a1b2c3d4e5f7
Revises: 8477c1466b70
Create Date: 2026-06-24 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = '8477c1466b70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create new table with email in PK
    op.create_table('campaign_recipients_new',
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['crm_email_campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('campaign_id', 'company_id', 'email'),
    )

    # 2. Expand existing rows: one row per active company email
    op.execute("""
        INSERT INTO campaign_recipients_new (campaign_id, company_id, email, added_at)
        SELECT cr.campaign_id, cr.company_id, ce.email, cr.added_at
        FROM campaign_recipients cr
        JOIN company_emails ce ON ce.company_id = cr.company_id
        WHERE ce.is_active = 1
    """)

    # 3. Drop old table
    op.drop_table('campaign_recipients')

    # 4. Rename new table
    op.rename_table('campaign_recipients_new', 'campaign_recipients')

    # 5. Recreate index
    op.create_index('ix_campaign_recipients_company', 'campaign_recipients', ['company_id'])


def downgrade() -> None:
    op.drop_index('ix_campaign_recipients_company')
    op.create_table('campaign_recipients_old',
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['crm_email_campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('campaign_id', 'company_id'),
    )

    # Collapse: one row per company (dedup by campaign_id, company_id)
    op.execute("""
        INSERT INTO campaign_recipients_old (campaign_id, company_id, added_at)
        SELECT DISTINCT campaign_id, company_id, MIN(added_at)
        FROM campaign_recipients
        GROUP BY campaign_id, company_id
    """)

    op.drop_table('campaign_recipients')
    op.rename_table('campaign_recipients_old', 'campaign_recipients')
    op.create_index('ix_campaign_recipients_company', 'campaign_recipients', ['company_id'])
