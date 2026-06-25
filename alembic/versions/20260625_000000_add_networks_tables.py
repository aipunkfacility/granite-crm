"""add networks tables and network_id columns

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f7
Create Date: 2026-06-25 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("networks")
    op.create_table(
        "networks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("base_domain", sa.String(), nullable=False, unique=True),
        sa.Column("signal_type", sa.String(), nullable=False, server_default="website"),
        sa.Column("network_type", sa.String(), nullable=False, server_default="franchise"),
        sa.Column("subdomains", sa.JSON(), server_default="[]"),
        sa.Column("emails", sa.JSON(), server_default="[]"),
        sa.Column("phones", sa.JSON(), server_default="[]"),
        sa.Column("company_count", sa.Integer(), server_default="0"),
        sa.Column("city_count", sa.Integer(), server_default="0"),
        sa.Column("cities", sa.JSON(), server_default="[]"),
        sa.Column("avg_score", sa.Float(), server_default="0.0"),
        sa.Column("segment_dist", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "network_email_toggles",
        sa.Column("network_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("is_disabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("reason", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("network_id", "email"),
        sa.ForeignKeyConstraint(["network_id"], ["networks.id"], ondelete="CASCADE"),
    )

    with op.batch_alter_table("enriched_companies") as batch_op:
        batch_op.drop_index("ix_enriched_companies_network_group")
        batch_op.drop_column("network_group")
        batch_op.add_column(sa.Column("network_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_enriched_companies_network_id",
            "networks",
            ["network_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_enriched_companies_network_id", ["network_id"])

    with op.batch_alter_table("campaign_recipients") as batch_op:
        batch_op.add_column(sa.Column("network_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_campaign_recipients_network_id",
            "networks",
            ["network_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("campaign_recipients") as batch_op:
        batch_op.drop_constraint("fk_campaign_recipients_network_id", type_="foreignkey")
        batch_op.drop_column("network_id")

    with op.batch_alter_table("enriched_companies") as batch_op:
        batch_op.drop_index("ix_enriched_companies_network_id")
        batch_op.drop_constraint("fk_enriched_companies_network_id", type_="foreignkey")
        batch_op.drop_column("network_id")
        batch_op.add_column(sa.Column("network_group", sa.String(), nullable=True))
        batch_op.create_index("ix_enriched_companies_network_group", ["network_group"])

    op.drop_table("network_email_toggles")
    op.drop_table("networks")
