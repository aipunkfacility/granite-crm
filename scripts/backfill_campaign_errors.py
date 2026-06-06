"""One-time backfill: подсчитать существующие bounce-логи и обновить campaign.total_errors.

Usage:
    uv run python -m scripts.backfill_campaign_errors

Безопасен для повторного запуска — использует MAX(current, count) чтобы не задвоить.
"""
from sqlalchemy import func
from granite.database import Database, CrmEmailLogRow, CrmEmailCampaignRow


def backfill():
    db = Database()
    with db.session_scope() as s:
        rows = (
            s.query(CrmEmailLogRow.campaign_id, func.count(CrmEmailLogRow.id))
            .filter(CrmEmailLogRow.status == "bounced")
            .filter(CrmEmailLogRow.campaign_id.isnot(None))
            .group_by(CrmEmailLogRow.campaign_id)
            .all()
        )

        if not rows:
            print("Нет bounce-логов для backfill.")
            return

        for campaign_id, bounce_count in rows:
            campaign = s.get(CrmEmailCampaignRow, campaign_id)
            if campaign:
                old = campaign.total_errors or 0
                campaign.total_errors = max(old, bounce_count)
                print(
                    f"campaign {campaign_id} ({campaign.name}): "
                    f"total_errors {old} -> {campaign.total_errors}"
                )

        print(f"Обработано кампаний: {len(rows)}")


if __name__ == "__main__":
    backfill()
