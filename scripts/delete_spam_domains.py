#!/usr/bin/env python3
"""Soft-delete companies on confirmed spam domains.

Запуск: uv run python scripts/delete_spam_domains.py
"""

import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone
from granite.database import Database, CompanyRow, EnrichedCompanyRow
from sqlalchemy import or_


SPAM_DOMAINS_TO_DELETE = frozenset({
    "acbank.ru", "mvd-kbr.ru", "lotgame.ru", "stroinas.ru",
    "online-obuchenie.ru", "rosbaltnord.ru", "energogazeta.ru",
    "help-tel.ru", "2sp.me",
})


def main():
    db = Database(auto_migrate=False)
    now = datetime.now(timezone.utc)

    with db.session_scope() as session:
        patterns = [
            CompanyRow.website.like(f"%{d}%")
            for d in SPAM_DOMAINS_TO_DELETE
        ]
        companies = session.query(CompanyRow).filter(or_(*patterns)).all()
        company_ids = [c.id for c in companies]

        print(f"Found {len(company_ids)} companies to soft-delete")

        for comp in companies:
            comp.deleted_at = now
            comp.needs_review = True
            comp.review_reason = (comp.review_reason + " spam_domain_cleanup").strip()
            comp.segment = "spam"

        if company_ids:
            ec_ids = [
                r[0] for r in session.query(EnrichedCompanyRow.id)
                .filter(EnrichedCompanyRow.id.in_(company_ids))
                .all()
            ]
            session.query(EnrichedCompanyRow).filter(
                EnrichedCompanyRow.id.in_(ec_ids)
            ).update(
                {
                    EnrichedCompanyRow.is_network: False,
                    EnrichedCompanyRow.segment: "spam",
                    EnrichedCompanyRow.crm_score: 0,
                },
                synchronize_session=False,
            )

        print(f"Soft-deleted {len(company_ids)} companies")

    print("Done!")


if __name__ == "__main__":
    main()
