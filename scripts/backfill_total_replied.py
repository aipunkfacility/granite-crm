"""One-time backfill: восстановить total_replied для существующих кампаний.

Usage:
    uv run python -m scripts.backfill_total_replied

Считает реальное количество reply-записей в crm_email_logs
(status='replied', campaign_id IS NOT NULL) и проставляет в кампанию.
"""
from sqlalchemy import func
from granite.database import Database, CrmEmailLogRow, CrmEmailCampaignRow


def backfill():
    db = Database()
    with db.session_scope() as s:
        campaigns = s.query(CrmEmailCampaignRow).all()
        updated = 0

        for campaign in campaigns:
            actual = (
                s.query(func.count(CrmEmailLogRow.id))
                .filter(
                    CrmEmailLogRow.campaign_id == campaign.id,
                    CrmEmailLogRow.status == "replied",
                )
                .scalar()
                or 0
            )

            old = campaign.total_replied or 0
            if actual != old:
                campaign.total_replied = actual
                updated += 1
                print(
                    f"campaign {campaign.id} ({campaign.name}): "
                    f"total_replied {old} -> {actual}"
                )

        print(f"Обновлено кампаний: {updated}")


if __name__ == "__main__":
    backfill()
