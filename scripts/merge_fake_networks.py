"""Merge all single-city same-name website duplicates into one company each.

Usage:
    uv run python scripts/merge_fake_networks.py --dry-run   # preview only
    uv run python scripts/merge_fake_networks.py              # execute
"""

import sys
import argparse
from datetime import datetime, timezone
from collections import Counter

from granite.database import Database, CompanyRow, CrmContactRow, EnrichedCompanyRow
from sqlalchemy import func


def pick_best(companies: list[CompanyRow], db_session) -> CompanyRow:
    """Pick best: max contacts, then highest crm_score, then earliest id."""
    def score(c: CompanyRow) -> tuple:
        contact_count = len(c.phones or []) + len(c.emails or [])
        enriched = db_session.get(EnrichedCompanyRow, c.id)
        s = enriched.crm_score if enriched else 0
        return (contact_count, s or 0, -c.id)
    return max(companies, key=score)


def merge_companies(target: CompanyRow, sources: list[CompanyRow], db_session) -> int:
    merged_count = 0
    for source in sources:
        if source.id == target.id:
            continue

        source.merged_into = target.id
        source.deleted_at = datetime.now(timezone.utc)
        source.review_reason = f"merged_into_{target.id}"

        if source.phones:
            target_phones = set(target.phones or [])
            added = [p for p in source.phones if p not in target_phones]
            if added:
                target_phones.update(added)
                target.phones = list(target_phones)

        if source.emails:
            target_emails = set(target.emails or [])
            added = [e for e in source.emails if e not in target_emails]
            if added:
                target_emails.update(added)
                target.emails = list(target_emails)

        # 5. Clear network flag on target after merging all sources
        target_enriched = db_session.get(EnrichedCompanyRow, target.id)
        if target_enriched and target_enriched.is_network:
            target_enriched.is_network = False

        merged_from = list(target.merged_from or [])
        if source.id not in merged_from:
            merged_from.append(source.id)
        target.merged_from = merged_from

        source_contact = db_session.get(CrmContactRow, source.id)
        if source_contact:
            target_contact = db_session.get(CrmContactRow, target.id)
            if target_contact:
                target_contact.contact_count = (
                    (target_contact.contact_count or 0) + (source_contact.contact_count or 0)
                )

        source_sources = source.sources or []
        target_sources = set(target.sources or [])
        for s in source_sources:
            target_sources.add(s)
        target.sources = sorted(target_sources)

        merged_count += 1

    target.updated_at = datetime.now(timezone.utc)
    return merged_count


def main():
    parser = argparse.ArgumentParser(description="Merge single-city same-name website duplicates")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no changes")
    args = parser.parse_args()

    db = Database()
    with db.session_scope() as s:
        site_groups = s.query(
            CompanyRow.website,
            func.count(CompanyRow.id).label('cnt'),
            func.count(func.distinct(CompanyRow.city)).label('cities'),
        ).filter(
            CompanyRow.website.isnot(None), CompanyRow.website != '',
            CompanyRow.deleted_at.is_(None), CompanyRow.merged_into.is_(None),
        ).group_by(CompanyRow.website).having(func.count(CompanyRow.id) > 1).all()

        single_city = [g for g in site_groups if g.cities == 1]
        total_merged = 0
        total_groups = 0

        kept_groups = 0
        kept_companies = 0

        for g in sorted(single_city, key=lambda x: -x.cnt):
            companies = s.query(CompanyRow).filter(
                CompanyRow.website == g.website,
                CompanyRow.deleted_at.is_(None), CompanyRow.merged_into.is_(None)
            ).all()

            names = set(c.name_best for c in companies)
            if len(names) != 1:
                continue  # skip multi-name groups (needs human review)
            kept_groups += 1
            kept_companies += g.cnt

            city = companies[0].city
            name = companies[0].name_best
            best = pick_best(companies, s)
            sources = [c for c in companies if c.id != best.id]

            if args.dry_run:
                print(f"[DRY-RUN] {city:<15} | {name:<35} | {g.cnt} companies -> keep ID {best.id}, merge {len(sources)}")
            else:
                count = merge_companies(best, sources, s)
                total_merged += count
                total_groups += 1
                print(f"  Merged {city:<15} | {name:<35} | {count} sources into ID {best.id}")

        if args.dry_run:
            removed = kept_companies - kept_groups
            print(f"\nWould merge {kept_groups} groups (~{removed} companies removed). "
                  f"Skipped {len(single_city) - kept_groups} multi-name groups (needs review).")
        else:
            print(f"\nDone. Merged {total_merged} sources in {total_groups} groups.")


if __name__ == "__main__":
    main()
