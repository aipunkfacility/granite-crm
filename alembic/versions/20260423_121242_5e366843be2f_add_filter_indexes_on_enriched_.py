"""add filter indexes on enriched_companies and companies

Revision ID: 5e366843be2f
Revises: 66ae407bd723
Create Date: 2026-04-23 12:12:42.795811

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e366843be2f'
down_revision: Union[str, None] = '66ae407bd723'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Составной индекс для типичного запроса: фильтр по segment + sort по is_network
    op.create_index(
        'ix_enriched_segment_network',
        'enriched_companies',
        ['segment', 'is_network'],
    )
    # Индекс для CMS-фильтра
    op.create_index(
        'ix_enriched_cms',
        'enriched_companies',
        ['cms'],
    )
    # Индекс для has_marquiz-фильтра
    op.create_index(
        'ix_enriched_marquiz',
        'enriched_companies',
        ['has_marquiz'],
    )
    # Составной индекс: фильтр по городу + soft-delete (каждый запрос)
    op.create_index(
        'ix_companies_city_deleted',
        'companies',
        ['city', 'deleted_at'],
    )
    # Индекс для needs_review-фильтра
    op.create_index(
        'ix_companies_needs_review',
        'companies',
        ['needs_review'],
    )


def downgrade() -> None:
    op.drop_index('ix_companies_needs_review', table_name='companies')
    op.drop_index('ix_companies_city_deleted', table_name='companies')
    op.drop_index('ix_enriched_marquiz', table_name='enriched_companies')
    op.drop_index('ix_enriched_cms', table_name='enriched_companies')
    op.drop_index('ix_enriched_segment_network', table_name='enriched_companies')
