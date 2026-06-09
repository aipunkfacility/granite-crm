#!/usr/bin/env python3
"""Batch merge companies sharing the same website domain + common email.

Usage:
    uv run python scripts/dedup_by_website.py                  # dry-run
    uv run python scripts/dedup_by_website.py --apply          # apply
    uv run python scripts/dedup_by_website.py --apply --rescan # apply + rescan
"""

import argparse
import sys
sys.path.insert(0, '.')
from collections import defaultdict
from datetime import datetime, timezone

from loguru import logger

from granite.database import Database, CompanyRow, EnrichedCompanyRow
from granite.utils import extract_domain


EXCLUDED_DOMAINS = frozenset({"danila-master.ru"})

_SEO_KEYWORDS = [
    "каталог", "цена", "стоим", "заказать", "купить", "контакты",
    "изготовление", "услуги", "регионы обслуживания",
]


def _is_seo_name(name: str) -> bool:
    name_lower = name.lower()
    return any(kw in name_lower for kw in _SEO_KEYWORDS)


def normalize_website(url: str | None) -> str | None:
    if not url:
        return None
    return extract_domain(url)


def should_merge_group(emails_list: list[list[str]]) -> bool:
    non_empty = [set(e) for e in emails_list if e]
    if not non_empty:
        return True
    common = set.intersection(*non_empty)
    return len(common) > 0


def completeness_score(comp: dict) -> int:
    score = 0
    name = comp.get("name_best") or ""
    if name:
        score += 2
        if _is_seo_name(name):
            score -= 1
    if comp.get("phones"):
        score += 2
    if comp.get("emails"):
        score += 3
    if comp.get("website"):
        score += 1
    if comp.get("messengers"):
        score += 2
    return score


def pick_target(comps: list[dict]) -> dict:
    best = max(comps, key=completeness_score)
    tied = [c for c in comps if completeness_score(c) == completeness_score(best)]
    if len(tied) > 1:
        with_email = [c for c in tied if c.get("emails")]
        if with_email:
            best = max(with_email, key=lambda c: len(c["emails"]))
        else:
            best = max(tied, key=lambda c: len(c.get("name_best") or ""))
    return best


def merge_group(db: Database, target_id: int, source_ids: list[int]):
    with db.session_scope() as session:
        target = session.get(CompanyRow, target_id)
        if not target:
            logger.error(f"Target #{target_id} not found")
            return

        now = datetime.now(timezone.utc)

        for sid in source_ids:
            source = session.get(CompanyRow, sid)
            if not source or source.deleted_at or source.merged_into:
                continue

            if source.phones:
                existing = set(target.phones or [])
                new_phones = [p for p in source.phones if p not in existing]
                if new_phones:
                    target.phones = (target.phones or []) + new_phones

            if source.emails:
                existing = set(target.emails or [])
                new_emails = [e for e in source.emails if e not in existing]
                if new_emails:
                    target.emails = (target.emails or []) + new_emails

            if source.messengers:
                target_m = dict(target.messengers or {})
                for k, v in (source.messengers or {}).items():
                    if k not in target_m:
                        target_m[k] = v
                target.messengers = target_m

            if source.sources:
                existing = set(target.sources or [])
                new_src = [s for s in source.sources if s not in existing]
                if new_src:
                    target.sources = (target.sources or []) + new_src

            source.merged_into = target_id
            source.deleted_at = now
            source.review_reason = f"dedup_by_website->#{target_id}"

            merged_from = list(target.merged_from or [])
            if sid not in merged_from:
                merged_from.append(sid)
            target.merged_from = merged_from

            enriched_source = session.get(EnrichedCompanyRow, sid)
            if enriched_source and enriched_source.is_network:
                enriched_source.is_network = False

        if target.needs_review:
            reasons = (target.review_reason or "").split()
            non_agg = [r for r in reasons if "aggregator_network" not in r]
            target.review_reason = " ".join(non_agg).strip()
            if not target.review_reason:
                target.needs_review = False

        target.updated_at = now


def mark_as_network(db: Database, company_ids: list[int]):
    with db.session_scope() as session:
        session.query(EnrichedCompanyRow).filter(
            EnrichedCompanyRow.id.in_(company_ids),
            EnrichedCompanyRow.is_network == False,
        ).update(
            {EnrichedCompanyRow.is_network: True},
            synchronize_session=False,
        )


def main():
    parser = argparse.ArgumentParser(description="Dedup companies by website domain")
    parser.add_argument("--apply", action="store_true", help="Apply merges (default: dry-run)")
    parser.add_argument("--rescan", action="store_true", help="Rescan networks after merge")
    args = parser.parse_args()

    db = Database(auto_migrate=False)

    with db.session_scope() as session:
        rows = session.query(
            CompanyRow.id, CompanyRow.name_best, CompanyRow.website,
            CompanyRow.phones, CompanyRow.emails, CompanyRow.messengers,
            CompanyRow.sources, CompanyRow.city,
            CompanyRow.needs_review, CompanyRow.review_reason,
            CompanyRow.merged_from,
        ).filter(
            CompanyRow.website.isnot(None),
            CompanyRow.website != "",
            CompanyRow.deleted_at.is_(None),
            CompanyRow.merged_into.is_(None),
        ).order_by(CompanyRow.id).all()

    companies = [
        {
            "id": r.id, "name_best": r.name_best, "website": r.website,
            "phones": r.phones or [], "emails": r.emails or [],
            "messengers": r.messengers or {}, "sources": r.sources or [],
            "city": r.city or "",
            "needs_review": r.needs_review, "review_reason": r.review_reason or "",
            "merged_from": r.merged_from or [],
        }
        for r in rows
    ]

    domain_groups: dict[str, list[dict]] = defaultdict(list)
    for comp in companies:
        domain = normalize_website(comp["website"])
        if not domain or domain in EXCLUDED_DOMAINS:
            continue
        domain_groups[domain].append(comp)

    to_merge: list[tuple[dict, list[dict]]] = []
    to_mark_network: list[list[int]] = []
    skipped_size_1 = 0

    for domain, comps in domain_groups.items():
        if len(comps) < 2:
            skipped_size_1 += 1
            continue

        emails_list = [list(comp.get("emails") or []) for comp in comps]

        if should_merge_group(emails_list):
            target = pick_target(comps)
            sources = [c for c in comps if c["id"] != target["id"]]
            to_merge.append((target, sources))
        else:
            to_mark_network.append([c["id"] for c in comps])

    total_multis = len(to_merge) + len(to_mark_network)
    total_sources = sum(len(s) for _, s in to_merge)

    print(f"\n{'='*60}")
    print(f"  Dedup by Website")
    print(f"{'='*60}")
    print(f"  Active companies with website:  {len(companies)}")
    print(f"  Unique domains:                 {len(domain_groups)}")
    print(f"  Groups with 2+ companies:       {total_multis}")
    print(f"    Merge:                        {len(to_merge):4} groups ({total_sources} source companies)")
    print(f"    Mark network:                 {len(to_mark_network):4} groups")
    print(f"    Skipped (size 1):             {skipped_size_1:4}")

    if to_merge:
        print(f"\n{'='*60}")
        print(f"  MERGE CANDIDATES")
        print(f"{'='*60}")
        for target, sources in sorted(to_merge, key=lambda x: -len(x[1])):
            domain = normalize_website(target["website"])
            t_emails = ",".join(target["emails"])
            print(f"  [{domain}] ({1+len(sources)} companies)")
            print(f"    target #{target['id']:5} | {target['name_best'] or '<no name>'}")
            print(f"      city={target['city'] or '?'}, phones={len(target['phones'])}, "
                  f"emails={t_emails or '<none>'}")
            if target["messengers"]:
                print(f"      messengers: {list(target['messengers'].keys())}")
            for s in sources:
                s_emails = ",".join(s["emails"])
                print(f"    source #{s['id']:5} | {s['name_best'] or '<no name>'}")
                print(f"      city={s['city'] or '?'}, phones={len(s['phones'])}, "
                      f"emails={s_emails or '<none>'}")
                if s["messengers"]:
                    print(f"      messengers: {list(s['messengers'].keys())}")

    if to_mark_network:
        print(f"\n{'='*60}")
        print(f"  NETWORK CANDIDATES (diff emails, NOT merged)")
        print(f"{'='*60}")
        for ids in sorted(to_mark_network, key=len, reverse=True)[:20]:
            c = next((x for x in companies if x["id"] == ids[0]), None)
            domain = normalize_website(c["website"]) if c else "?"
            info = []
            for cid in ids[:3]:
                c2 = next((x for x in companies if x["id"] == cid), None)
                if c2:
                    emails = ",".join(c2["emails"]) or "<no email>"
                    info.append(f"#{cid}({emails})")
            tail = f" ... +{len(ids)-3} more" if len(ids) > 3 else ""
            print(f"  {domain:30s} | {len(ids):3} companies | {'; '.join(info)}{tail}")
        if len(to_mark_network) > 20:
            print(f"  ... and {len(to_mark_network) - 20} more network groups")

    if not args.apply:
        print(f"\n{'='*60}")
        print(f"  DRY-RUN MODE - no changes made")
        print(f"  Run with --apply to execute")
        print(f"{'='*60}")
        return

    # -- APPLY --
    print(f"\n{'='*60}")
    print(f"  APPLYING...")
    print(f"{'='*60}")

    merged_total = 0
    for target, sources in to_merge:
        s_ids = [s["id"] for s in sources]
        merge_group(db, target["id"], s_ids)
        merged_total += len(s_ids)
        print(f"  Merged {len(s_ids)} sources into #{target['id']} ({target['name_best'] or '<no name>'})")

    for ids in to_mark_network:
        mark_as_network(db, ids)

    print(f"\n  Total merged: {merged_total} companies into {len(to_merge)} groups")
    print(f"  Total marked as network: {sum(len(ids) for ids in to_mark_network)} companies in "
          f"{len(to_mark_network)} groups")

    if args.rescan:
        print(f"\n  Rescanning networks...")
        from granite.enrichers.network_detector import NetworkDetector
        import yaml
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        detector = NetworkDetector(db, config)
        detector.scan_for_networks()

        from granite.dedup.network_filter import detect_and_mark_aggregators
        detect_and_mark_aggregators(db)

    print(f"\n{'='*60}")
    print(f"  DONE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
