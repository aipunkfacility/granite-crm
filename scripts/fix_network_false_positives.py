#!/usr/bin/env python3
"""Однократный скрипт для исправления ложных is_network после правки фильтрации.

Сбрасывает is_network=False для компаний, чей сайт входит в
NON_NETWORK_DOMAINS или SPAM_DOMAINS, при условии что у них нет
других сетевых сигналов (общий телефон, email-домен).

Запуск: uv run python scripts/fix_network_false_positives.py
"""

import sys
sys.path.insert(0, '.')

from granite.database import Database
from granite.enrichers.network_detector import NetworkDetector
from granite.dedup.network_filter import detect_and_mark_aggregators
from granite.constants import NON_NETWORK_DOMAINS, SPAM_DOMAINS


def main():
    db = Database(auto_migrate=False)

    print("Step 1: Removing is_network from NON_NETWORK_DOMAINS websites...")
    with db.session_scope() as session:
        from granite.database import EnrichedCompanyRow
        from sqlalchemy import or_

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
