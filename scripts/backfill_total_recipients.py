"""One-time backfill: восстановить total_recipients для существующих кампаний.

Usage:
    uv run python -m scripts.backfill_total_recipients

Для manual-кампаний: total_recipients = количество записей в campaign_recipients.
Для filter-кампаний: total_recipients = max(stored, total_sent).
"""
from granite.database import (
    Database, CrmEmailCampaignRow, CampaignRecipientRow,
)


def backfill():
    db = Database()
    with db.session_scope() as s:
        campaigns = s.query(CrmEmailCampaignRow).all()
        updated = 0

        for campaign in campaigns:
            old = campaign.total_recipients or 0
            total = 0

            if campaign.recipient_mode == "manual":
                total = s.query(CampaignRecipientRow).filter_by(
                    campaign_id=campaign.id
                ).count()
            else:
                total = max(old, campaign.total_sent or 0)

            if total > 0 and total != old:
                campaign.total_recipients = total
                updated += 1
                print(
                    f"campaign {campaign.id} ({campaign.name}): "
                    f"{old} -> {total} ({campaign.recipient_mode})"
                )

        print(f"Обновлено кампаний: {updated}")


if __name__ == "__main__":
    backfill()
