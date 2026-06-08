"""Analyze remaining network groups for intra-city duplicates.
Run: uv run python scripts/analyze_network_dupes.py
"""
from collections import defaultdict
from sqlalchemy import func
from granite.database import Database, CompanyRow


def main():
    db = Database()
    with db.session_scope() as s:
        site_groups = s.query(
            CompanyRow.website,
            func.count(CompanyRow.id).label("cnt"),
            func.count(func.distinct(CompanyRow.city)).label("cities"),
        ).filter(
            CompanyRow.website.isnot(None),
            CompanyRow.website != "",
            CompanyRow.deleted_at.is_(None),
            CompanyRow.merged_into.is_(None),
        ).group_by(CompanyRow.website).having(
            func.count(CompanyRow.id) > 1
        ).all()

        single_city = [g for g in site_groups if g.cities == 1]
        multi_city = [g for g in site_groups if g.cities > 1]

        print(f"\n{'='*60}")
        print(f"  NETWORK DUPLICATE ANALYSIS")
        print(f"{'='*60}")
        print(f"\nTotal website groups with 2+ companies: {len(site_groups)}")
        print(f"  Single-city: {len(single_city)}")
        print(f"  Multi-city:  {len(multi_city)}")
        print(f"\nAlready processed: 28 same-name single-city groups merged, 116 removed")

        # ── Section 1: 20 mixed-name single-city groups ──
        print(f"\n{'─'*60}")
        print(f"  SECTION 1: Single-city, mixed names (20 groups, 66 companies)")
        print(f"{'─'*60}")
        print()
        print(f"{'Group':<55} {'City':<15} {'Type'}")
        print(f"{'─'*85}")

        for g in sorted(single_city, key=lambda x: -x.cnt):
            companies = s.query(
                CompanyRow.id, CompanyRow.name_best, CompanyRow.city
            ).filter(
                CompanyRow.website == g.website,
                CompanyRow.deleted_at.is_(None),
                CompanyRow.merged_into.is_(None),
            ).all()

            names = set(c.name_best for c in companies)
            if len(names) <= 1:
                continue

            city = companies[0].city
            # Classify
            clean_names = [n for n in names if not any(
                kw in n.lower() for kw in [
                    "изготовление", "купить", "цены", "главная",
                    "компания", "о компании", "услуги", "предложения"
                ])]
            seo_only = len(clean_names) <= 1
            tag = "SEO-DUPE" if seo_only else "MIXED"

            print(f"{g.website:<55} {city:<15} [{tag}]")
            for c in sorted(companies, key=lambda x: x.name_best):
                print(f"  {'':>50} ID {c.id:>4} | {c.name_best}")

        # ── Section 2: Multi-city with intra-city dupes ──
        print(f"\n{'─'*60}")
        print(f"  SECTION 2: Multi-city networks with same-city duplicates")
        print(f"{'─'*60}")
        print()

        total_extra = 0
        for g in sorted(multi_city, key=lambda x: -x.cnt):
            companies = s.query(
                CompanyRow.id, CompanyRow.name_best, CompanyRow.city
            ).filter(
                CompanyRow.website == g.website,
                CompanyRow.deleted_at.is_(None),
                CompanyRow.merged_into.is_(None),
            ).all()

            by_city = defaultdict(list)
            for c in companies:
                by_city[c.city].append(c)

            group_extra = 0
            dup_cities = {}
            for city, clist in by_city.items():
                if len(clist) > 1:
                    names = set(c.name_best for c in clist)
                    if len(names) == 1:
                        group_extra += len(clist) - 1
                        dup_cities[city] = (len(clist), clist[0].name_best)

            if group_extra > 0:
                total_extra += group_extra
                print(f"Site: {g.website}")
                print(f"  Total: {g.cnt} comp / {g.cities} cities")
                for city, (cnt, name) in sorted(dup_cities.items()):
                    print(f"  DUP: {city}: {cnt}x \"{name}\"")
                print()

        print(f"Total intra-city duplicates in multi-city networks: ~{total_extra}")

        # ── Section 3: Summary ──
        print(f"\n{'='*60}")
        print(f"  SUMMARY")
        print(f"{'='*60}")
        total_website_dupes = 116  # already merged
        total_mixed_remaining = sum(
            g.cnt - 1
            for g in single_city
            if len(set(
                c.name_best for c in s.query(CompanyRow.name_best).filter(
                    CompanyRow.website == g.website,
                    CompanyRow.deleted_at.is_(None),
                    CompanyRow.merged_into.is_(None),
                ).all()
            )) > 1
        )
        print(f"\n  Already removed:           {total_website_dupes:>4}")
        print(f"  Mixed-name remaining:      {total_mixed_remaining:>4} (needs review)")
        print(f"  Multi-city intra dupes:    {total_extra:>4} (same name, safe to merge)")
        print(f"  Total addressable:         {total_website_dupes + total_extra:>4}")
        print(f"  Clean real networks:       {len(multi_city) - 13}")  # 13 had intra dupes
        print()


if __name__ == "__main__":
    main()
