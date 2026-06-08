"""Merge duplicate companies sharing the same website domain + city.

Usage:
    uv run python scripts/merge_duplicates_by_domain.py obitel-pamyatnik.ru
    uv run python scripts/merge_duplicates_by_domain.py obitel-pamyatnik.ru --city "Саратов" --dry-run
"""

import sys
import argparse
from datetime import datetime, timezone

from granite.database import Database, CompanyRow, CrmContactRow, EnrichedCompanyRow
from sqlalchemy import func


def pick_best(companies: list[CompanyRow], db_session) -> CompanyRow:
    """Pick the best record: max(phones + emails), tie-break by highest crm_score."""
    def score(c: CompanyRow) -> tuple:
        contact_count = len(c.phones or []) + len(c.emails or [])
        enriched = db_session.get(EnrichedCompanyRow, c.id)
        s = enriched.crm_score if enriched else 0
        return (contact_count, s or 0)
    return max(companies, key=score)


def merge_companies(target: CompanyRow, sources: list[CompanyRow], db_session) -> int:
    """Merge source companies into target. Returns count of merged sources."""
    merged_count = 0
    for source in sources:
        if source.id == target.id:
            continue

        source.merged_into = target.id
        source.deleted_at = datetime.now(timezone.utc)
        source.review_reason = f"merged_into_{target.id}"

        # Merge phones
        if source.phones:
            target_phones = set(target.phones or [])
            added = [p for p in source.phones if p not in target_phones]
            if added:
                target_phones.update(added)
                target.phones = list(target_phones)

        # Merge emails
        if source.emails:
            target_emails = set(target.emails or [])
            added = [e for e in source.emails if e not in target_emails]
            if added:
                target_emails.update(added)
                target.emails = list(target_emails)

        # Update merged_from
        merged_from = list(target.merged_from or [])
        if source.id not in merged_from:
            merged_from.append(source.id)
        target.merged_from = merged_from

        # Merge CRM contact
        source_contact = db_session.get(CrmContactRow, source.id)
        if source_contact:
            target_contact = db_session.get(CrmContactRow, target.id)
            if target_contact:
                target_contact.contact_count = (
                    (target_contact.contact_count or 0) + (source_contact.contact_count or 0)
                )

        # Merge sources
        source_sources = source.sources or []
        target_sources = set(target.sources or [])
        for s in source_sources:
            target_sources.add(s)
        target.sources = sorted(target_sources)

        merged_count += 1
        print(f"  Merged ID {source.id} ({source.name_best}) -> ID {target.id} ({target.name_best})")

    target.updated_at = datetime.now(timezone.utc)
    return merged_count


def main():
    parser = argparse.ArgumentParser(description="Merge duplicate companies by website domain")
    parser.add_argument("domain", help="Website domain (e.g. obitel-pamyatnik.ru)")
    parser.add_argument("--city", help="Filter by city (optional)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be merged without doing it")
    args = parser.parse_args()

    like = f"%{args.domain}%"

    db = Database()
    with db.session_scope() as s:
        q = s.query(CompanyRow).filter(
            CompanyRow.website.ilike(like),
            CompanyRow.deleted_at.is_(None),
        )

        if args.city:
            q = q.filter(CompanyRow.city.ilike(f"%{args.city}%"))

        companies = q.order_by(CompanyRow.city, CompanyRow.name_best).all()

        if not companies:
            print(f"No active companies found with domain '{args.domain}'")
            return

        print(f"Found {len(companies)} active companies with domain '{args.domain}':")
        for c in companies:
            phones = len(c.phones or [])
            emails = len(c.emails or [])
            enriched = s.get(EnrichedCompanyRow, c.id)
            score_val = enriched.crm_score if enriched else 0
            print(f"  ID {c.id:>5} | {c.name_best:<40} | {c.city:<15} | phones={phones} emails={emails} score={score_val}")

        print()

        # Group by city
        groups: dict[str, list[CompanyRow]] = {}
        for c in companies:
            groups.setdefault(c.city, []).append(c)

        total_merged = 0
        for city, group in groups.items():
            if len(group) < 2:
                continue

            best = pick_best(group, s)
            sources = [c for c in group if c.id != best.id]

            enriched = s.get(EnrichedCompanyRow, best.id)
            score_val = enriched.crm_score if enriched else 0
            print(f"City: {city}")
            print(f"  Best: ID {best.id} ({best.name_best}) — {len(best.phones or [])} phones, {len(best.emails or [])} emails, score={score_val}")
            print(f"  Sources: {[c.id for c in sources]}")

            if args.dry_run:
                print(f"  (dry-run, would merge {len(sources)} records)")
            else:
                count = merge_companies(best, sources, s)
                total_merged += count
                print(f"  Merged {count} records")
            print()

        if total_merged > 0 or args.dry_run:
            print(f"Done. {'(dry-run) ' if args.dry_run else ''}Merged {total_merged} duplicates.")


if __name__ == "__main__":
    main()
