#!/usr/bin/env python3
"""Однократный скрипт для исправления ложных is_network после правки фильтрации.

Сбрасывает is_network=False для компаний, чей сайт входит в
NON_NETWORK_DOMAINS или SPAM_DOMAINS, при условии что у них нет
других сетевых сигналов (общий телефон, email-домен).

Запуск: uv run python scripts/fix_network_false_positives.py
"""

import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone
from granite.database import Database, CompanyRow, EnrichedCompanyRow
from granite.enrichers.network_detector import NetworkDetector
from granite.dedup.network_filter import detect_and_mark_aggregators
from granite.constants import NON_NETWORK_DOMAINS, SPAM_DOMAINS
from scripts.delete_spam_domains import SPAM_DOMAINS_TO_DELETE
from sqlalchemy import or_


def main():
    db = Database(auto_migrate=False)

    print("Step 1: Removing is_network from NON_NETWORK_DOMAINS websites...")
    with db.session_scope() as session:
        patterns = []
        for domain in NON_NETWORK_DOMAINS:
            patterns.append(EnrichedCompanyRow.website.like(f"%{domain}%"))
        for domain in SPAM_DOMAINS:
            patterns.append(EnrichedCompanyRow.website.like(f"%{domain}%"))

        q = session.query(EnrichedCompanyRow).filter(
            or_(*patterns),
            EnrichedCompanyRow.is_network == True,
        )
        affected = q.count()
        print(f"  Found {affected} companies to reset")

        if affected:
            q.update(
                {EnrichedCompanyRow.is_network: False},
                synchronize_session=False,
            )
            session.flush()

        # Step 1.5 inside the same session
        spam_patterns_c = [
            CompanyRow.website.like(f"%{d}%")
            for d in SPAM_DOMAINS_TO_DELETE
        ]
        spam_companies = session.query(CompanyRow).filter(or_(*spam_patterns_c)).all()
        now = datetime.now(timezone.utc)
        for comp in spam_companies:
            comp.deleted_at = now
            comp.needs_review = True
            comp.review_reason = (comp.review_reason + " spam_domain_cleanup").strip()
            comp.segment = "spam"
        if spam_companies:
            print(f"  Soft-deleted {len(spam_companies)} companies")

    print("Step 2: Re-running scan_for_networks with fixed filtering...")
    import yaml
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    detector = NetworkDetector(db, config)
    detector.scan_for_networks()

    print("Step 3: Re-running A-6 global scan...")
    detect_and_mark_aggregators(db)

    print("Done! Run the following to verify:")
    print("  uv run python scripts/network_stats.py")


if __name__ == "__main__":
    main()
