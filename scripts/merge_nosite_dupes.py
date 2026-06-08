"""Batch 3: merge same-name same-city no-site duplicate groups (~130 companies).

Usage:
    uv run python scripts/merge_nosite_dupes.py --dry-run
    uv run python scripts/merge_nosite_dupes.py
"""
import argparse
from granite.database import Database, CompanyRow
from scripts.merge_fake_networks import merge_companies


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    groups = [
        ("Памятники", "Жуков", 2539),
        ("Вечность", "Жуков", 2540),
        ("Ритуал", "Жуков", 2541),
        ("Памятники", "Пушкино", 6179),
        ("Памятники", "Советск", 6872),
        ("Ритуал", "Комсомольск", 4389),
        ("Мастерская по изготовлению памятников и оград", "Невель", 4860),
        ("Ритуал Наволоки", "Энгельс", 4792),
        ("Ритуальные услуги", "Советск", 3711),
        ("Черная Роза", "Невель", 4859),
        ("Гранит", "Маркс", 7968),
        ("Памятники", "Маркс", 1031),
        ("Ритуальные услуги", "Первомайск", 3650),
        ("Изготовление памятников", "Маркс", 4694),
        ("Изготовление памятников", "Советск", 415),
        ("Памятники", "Гагарин", 5184),
        ("Памятники", "Красноармейск", 6135),
        ("Памятники и надгробия", "Комсомольск", 3139),
        ("Ритуал-сервис", "Октябрьск", 1225),
        ("Ритуальные услуги", "Комсомольск", 7645),
        ("Rakovinaray", "Владикавказ", 1618),
        ("Век", "Киров", 478),
        ("Вечность ритуальный салон", "Красноармейск", 1340),
        ("Военно-мемориальная компания", "Мурманск", 3124),
        ("Гранит", "Владикавказ", 1625),
        ("Гранит", "Октябрьск", 5563),
        ("Гранитная мастерская", "Октябрьск", 3554),
        ("Гранитная мастерская", "Советск", 8323),
        ("Доверие Агентство ритуальных услуг", "Лысково", 4272),
        ("Изготовление памятников", "Кропоткин", 3870),
        ("Изготовление памятников", "Лермонтов", 4099),
        ("Изготовление памятников и надгробий", "Первомайск", 5230),
        ("Мастерская по изготовлению памятников", "Красноармейск", 980),
        ("Обелиск", "Комсомольск", 2095),
        ("Памятники", "Благовещенск", 1142),
        ("Памятники", "Первомайск", 1921),
        ("Памятники", "Пролетарск", 5248),
        ("Памятники", "Строитель", 671),
        ("Памятники и надгробия", "Маркс", 4041),
        ("Память", "Пролетарск", 7836),
        ("Ритуал", "Михайлов", 4597),
        ("Ритуальная служба", "Красноармейск", 1508),
        ("Ритуальные товары", "Маркс", 7584),
        ("Ритуальные услуги", "Гагарин", 114),
        ("Ритуальные услуги", "Михайлов", 4585),
        ("Ритуальные услуги", "Пушкино", 1741),
        ("Ритуальный магазин", "Советск", 7450),
        ("Салон ритуальных услуг", "Владикавказ", 1635),
        ("Стела", "Маркс", 7958),
        ("Стелла", "Советск", 2912),
    ]

    db = Database()
    with db.session_scope() as s:
        total_sources = 0
        total_groups = 0

        for name, city, keep_id in groups:
            companies = s.query(CompanyRow).filter(
                CompanyRow.name_best == name,
                CompanyRow.city == city,
                CompanyRow.deleted_at.is_(None),
                CompanyRow.merged_into.is_(None),
            ).all()

            target = next((c for c in companies if c.id == keep_id), None)
            if not target:
                print(f"SKIP: \"{name[:30]}\" ({city}) — target ID {keep_id} not found")
                continue

            sources = [c for c in companies if c.id != keep_id]
            if not sources:
                print(f"SKIP: \"{name[:30]}\" ({city}) — no sources")
                continue

            total_groups += 1
            total_sources += len(sources)

            if args.dry_run:
                print(f"[DRY-RUN] \"{name[:30]:30s}\" ({city:15s}) keep {keep_id}, merge {len(sources)}")
            else:
                cnt = merge_companies(target, sources, s)
                print(f"Merged    \"{name[:30]:30s}\" ({city:15s}) keep {keep_id}, merged {cnt}")

        if args.dry_run:
            print(f"\nWould merge {total_sources} across {total_groups} groups (~{total_sources} removed)")
        else:
            print(f"\nDone. Merged {total_sources} across {total_groups} groups.")


if __name__ == "__main__":
    main()
