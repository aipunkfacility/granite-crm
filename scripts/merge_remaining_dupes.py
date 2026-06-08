"""Batch 2: merge remaining duplicate groups (38 groups, ~123 companies).

Groups:
  25 single-city SEO-DUPE/MIXED (same site+city, SEO titles + real names)
  13 multi-city intra-city (same site+city, same name repeated)

Usage:
    uv run python scripts/merge_remaining_dupes.py --dry-run
    uv run python scripts/merge_remaining_dupes.py
"""
import sys
import argparse
from datetime import datetime, timezone

from granite.database import Database, CompanyRow, CrmContactRow, EnrichedCompanyRow
from scripts.merge_fake_networks import merge_companies


def main():
    parser = argparse.ArgumentParser(
        description="Batch merge remaining 38 duplicate groups"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    groups = [
        # ── Single-city SEO-DUPE + MIXED (exact match analysis output) ──
        ("http://cheuzova.ru/", "Хабаровск", 7960),
        ("https://almem.ru/", "Майкоп", 68),
        ("https://arkado-granit.ru/", "Барнаул", 368),
        ("https://blagodel32.ru/", "Брянск", 656),
        ("https://gormemorial.ru/", "Москва", 1027),
        ("https://granit-export.ru/", "Донецк", 3003),
        ("https://granit51.ru/", "Красноармейск", 4640),
        ("https://granit-volga34.ru/", "Волгоград", 3727),
        ("https://kpam3d.ru/", "Арзамас", 4241),
        ("https://mir-granita26.ru/", "Ставрополь", 29),
        ("https://mirgranita31.ru/", "Белгород", 874),
        ("https://monument-stone.ru/", "Белореченск", 2106),
        ("https://monument123.ru/", "Белореченск", 2104),
        ("https://monumento.su/", "Подольск", 4747),
        ("https://obeliskm.ru/", "Москва", 2069),
        ("https://ooo-memorial.ru/", "Коломна", 3569),
        ("https://oren-mramor.ru/", "Оренбург", 3913),
        ("https://pamyatnik-42.ru/", "Белово", 491),
        ("https://s-lock.ru/", "Советск", 1381),
        ("https://uv2000.ru/", "Советск", 639),
        ("https://veles-stone.ru/", "Казань", 57),
        ("https://vladikavkaz.pamyatnik-granit.site/", "Владикавказ", 1628),
        ("https://xn-----7kcgcbbneasledd2akxofgfamcdbn2fl8kxl.xn--p1ai/", "Одинцово", 5527),
        ("https://xn----7sbq1aafcepuhi.xn--p1ai/", "Ярославль", 58),
        ("https://xn--34-6kc6akkhn3a3k.xn--p1ai/", "Волгоград", 44),

        # ── Multi-city intra-city dupes ──
        ("https://nikapamyatniki.ru/", "Воронеж", 963),
        ("https://granitplus48.ru/", "Коммунар", 2448),
        ("https://memorialservis.ru/", "Советск", 2451),
        ("https://www.vmkros.ru/", "Советск", 6522),
        ("https://granita-dvor.ru/", "Октябрьск", 7557),
        ("http://ritual37.ru/", "Комсомольск", 2569),
        ("https://dv-granit.ru/", "Владивосток", 654),
        ("https://diz-servis.ru/", "Советск", 6051),
        ("https://zavolzhsk.danila-master.ru/", "Иваново", 2570),
        ("https://vekrm.ru/", "Саранск", 5960),
        ("http://www.vrk-tmb.ru/", "Советск", 2513),
        ("https://granit44.ru/", "Кострома", 1638),
        ("https://kameshkovo.danila-master.ru/", "Ярославль", 3093),
    ]

    db = Database()
    with db.session_scope() as s:
        total_sources = 0
        total_groups = 0

        for site, city, keep_id in groups:
            companies = s.query(CompanyRow).filter(
                CompanyRow.website == site,
                CompanyRow.city == city,
                CompanyRow.deleted_at.is_(None),
                CompanyRow.merged_into.is_(None),
            ).all()

            target = next((c for c in companies if c.id == keep_id), None)
            if not target:
                print(f"SKIP: {site}  {city} — target ID {keep_id} not found")
                continue

            sources = [c for c in companies if c.id != keep_id]
            if not sources:
                print(f"SKIP: {site}  {city} — no sources (already merged)")
                continue

            total_groups += 1
            total_sources += len(sources)

            if args.dry_run:
                print(f"[DRY-RUN] {city:<20} keep ID {keep_id}, merge {len(sources)}")
                for src in sources:
                    name = (src.name_best or "")[:40]
                    print(f"           merge ID {src.id:>4} \"{name}\"")
            else:
                cnt = merge_companies(target, sources, s)
                print(f"Merged    {city:<20} keep ID {keep_id}, merged {cnt}")

        if args.dry_run:
            print(f"\nWould merge {total_sources} across {total_groups} groups "
                  f"(~{total_sources} removed)")
        else:
            print(f"\nDone. Merged {total_sources} across {total_groups} groups.")


if __name__ == "__main__":
    main()
