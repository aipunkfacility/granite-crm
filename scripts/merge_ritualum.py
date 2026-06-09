#!/usr/bin/env python3
"""Merge all ritualum.ru companies into #6933 (Sochi).

These are all the same federal call-center — same phone, same email.

Usage:
    uv run python scripts/merge_ritualum.py           # dry-run
    uv run python scripts/merge_ritualum.py --apply   # apply
"""

import argparse
import sys
sys.path.insert(0, '.')
from datetime import datetime, timezone

from sqlalchemy import or_

from granite.database import Database, CompanyRow, EnrichedCompanyRow


TARGET_ID = 6933
BASE_DOMAIN = "ritualum.ru"


def main():
    parser = argparse.ArgumentParser(description="Merge ritualum.ru into one company")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = Database(auto_migrate=False)

    with db.session_scope() as session:
        # Query all active ritualum.ru companies
        companies = session.query(CompanyRow).filter(
            CompanyRow.website.like(f"%{BASE_DOMAIN}%"),
            CompanyRow.deleted_at.is_(None),
            CompanyRow.merged_into.is_(None),
        ).order_by(CompanyRow.id).all()

        # Separate target from sources
        target = None
        sources = []
        for c in companies:
            if c.id == TARGET_ID:
                target = c
            else:
                sources.append(c)

        if not target:
            print(f"ERROR: Target #{TARGET_ID} not found or inactive")
            return 1

        print(f"\n{'='*60}")
        print(f"  Merge ritualum.ru -> #{TARGET_ID} ({target.city}, {target.name_best[:30]})")
        print(f"{'='*60}")
        print(f"  Target: #{TARGET_ID:5} | {target.city:20s} | {(target.website or '')[:35]:35s} | "
              f"ph={len(target.phones or [])} | em={len(target.emails or [])}")
        print(f"  Sources ({len(sources)} companies):")
        for c in sources:
            e = session.get(EnrichedCompanyRow, c.id)
            net = e.is_network if e else '?'
            print(f"    #{c.id:5} | {c.city or '?':20s} | {(c.website or '')[:35]:35s} | "
                  f"ph={len(c.phones or []):1d} | em={len(c.emails or []):1d} | net={net}")

        if not args.apply:
            print(f"\n  DRY-RUN — run with --apply to merge")
            return 0

        # -- APPLY --
        now = datetime.now(timezone.utc)

        t = session.get(CompanyRow, TARGET_ID)
        merged_count = 0
        for c in sources:
            s = session.get(CompanyRow, c.id)
            if not s or s.deleted_at or s.merged_into:
                continue

            # Merge phones
            if s.phones:
                existing = set(t.phones or [])
                new = [p for p in s.phones if p not in existing]
                if new:
                    t.phones = (t.phones or []) + new

            # Merge emails
            if s.emails:
                existing = set(t.emails or [])
                new = [e for e in s.emails if e not in existing]
                if new:
                    t.emails = (t.emails or []) + new

            # Mark source as merged
            s.merged_into = TARGET_ID
            s.deleted_at = now
            s.review_reason = f"merged_into_{TARGET_ID}_dedup"

            merged_from = list(t.merged_from or [])
            if c.id not in merged_from:
                merged_from.append(c.id)
            t.merged_from = merged_from

            # Clear is_network on source
            es = session.get(EnrichedCompanyRow, c.id)
            if es and es.is_network:
                es.is_network = False

            merged_count += 1

        t.updated_at = now
        session.flush()

        # Clear is_network on target too
        et = session.get(EnrichedCompanyRow, TARGET_ID)
        if et and et.is_network:
            et.is_network = False

        print(f"\n  Merged {merged_count} companies into #{TARGET_ID}")
        print(f"  is_network cleared on all ritualum.ru companies")

    print(f"  DONE")


if __name__ == "__main__":
    main()
