#!/usr/bin/env python3
"""
Валидация и очистка контактов в granite.db.

Проверяет email и телефоны во всех трёх таблицах (raw_companies, companies,
enriched_companies), удаляет мусор, помечает подозрительные записи.

Использование:
    python scripts/db_validate.py                     # отчёт без исправлений
    python scripts/db_validate.py --fix               # с исправлениями
    python scripts/db_validate.py --fix --db path.db  # другой путь к БД

Для json'а с протоколом:
    python scripts/db_validate.py --fix --json report.json
"""
import argparse
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# ── Конфигурация ──────────────────────────────────────────────────────────────

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "granite.db")

# TLD, которые НЕ являются email-доменами (файлы, изображения)
FAKE_TLDS = frozenset({
    "jpg", "jpeg", "png", "gif", "svg", "webp", "bmp", "ico", "tif", "tiff",
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip", "rar", "7z",
    "mp4", "avi", "mov", "mp3", "wav", "css", "js", "html", "htm", "xml",
    "woff", "woff2", "ttf", "otf", "eot",
})

# Локальные части email, которые явно не являются адресами
FAKE_LOCAL_PARTS = frozenset({
    "photo", "image", "icon", "logo", "favicon", "banner", "bg", "background",
    "thumbnail", "thumb", "avatar", "placeholder", "sample", "demo", "test",
    "example", "email", "username", "user", "admin", "webmaster", "postmaster",
    "noreply", "no-reply", "mailer-daemon", "abuse", "root",
    # изображения с @ (img@2x.domain.com)
    "img", "src", "assets", "static", "media", "files", "upload", "uploads",
})

# DEF-коды, которые точно не могут быть мобильными/городскими РФ
INVALID_DEF_CODES = frozenset({
    "000",  # полностью нулевой
})

# Подозрительные DEF-коды: вряд ли мелкие мастерские их используют
SUSPICIOUS_DEF_CODES = frozenset({
    "800",  # бесплатный (не мастерская)
})

# Лимиты контактов на одну компанию
MAX_EMAILS = 4
MAX_PHONES = 6

# Свободные email-провайдеры (для приоритизации company-domain email)
FREE_EMAIL_DOMAINS = frozenset({
    "mail.ru", "inbox.ru", "bk.ru", "list.ru", "yandex.ru", "ya.ru",
    "gmail.com", "googlemail.com", "hotmail.com", "outlook.com", "live.com",
    "rambler.ru", "yahoo.com", "protonmail.com", "zoho.com", "mail.com",
})

# Минимальная длина email local part
MIN_EMAIL_LOCAL_LEN = 3

# ── Валидаторы ────────────────────────────────────────────────────────────────


def validate_email(email: str) -> tuple[bool, str]:
    """Проверяет один email. Возвращает (valid, reason).

    Мусорные причины:
    - fake_tld        — TLD является расширением файла
    - fake_local      — локальная часть — явно не адрес
    - too_short_local — локальная часть слишком короткая
    - no_at           — нет @ (не email)
    - no_dot_in_domain — домен без точки
    - double_dot      — двойная точка
    - leading_dot     — начинается с точки
    - trailing_dot    — заканчивается точкой
    - has_plus_trick  — user+tag@domain (часто мусор из рассылок)
    """
    if not email or not isinstance(email, str):
        return False, "empty"

    email = email.strip().lower()

    # Базовый формат: что-то@что-то.что-то
    if "@" not in email:
        return False, "no_at"

    local, domain = email.rsplit("@", 1)

    if not local or not domain:
        return False, "empty_part"

    if "." not in domain:
        return False, "no_dot_in_domain"

    # Локальная часть слишком короткая
    if len(local) < MIN_EMAIL_LOCAL_LEN:
        return False, "too_short_local"

    # TLD — расширение файла?
    tld = domain.rsplit(".", 1)[-1].lower()
    if tld in FAKE_TLDS:
        return False, f"fake_tld:.{tld}"

    # Локальная часть — явно не адрес?
    local_base = local.split("+")[0]  # user+tag → user
    if local_base in FAKE_LOCAL_PARTS:
        return False, f"fake_local:{local_base}"

    # Паттерны мусора
    if ".." in email:
        return False, "double_dot"
    if local.startswith(".") or local.endswith("."):
        return False, "leading/trailing_dot"

    # Паттерны типа photo@2x.example.com (из атрибутов img в HTML)
    # local часть содержит цифры-суффиксы изображений
    img_pattern = re.match(r'^[a-z]+@\d+x?\.', email)
    if img_pattern:
        return False, "img_pattern"

    return True, "ok"


def validate_phone(phone: str) -> tuple[bool, str]:
    """Проверяет один телефон (E.164: 7XXXXXXXXXX).

    Мусорные причины:
    - wrong_length    — не 11 цифр
    - wrong_prefix    — не начинается с 7
    - invalid_def     — DEF-код невалидный (000)
    - suspicious_def  — подозрительный DEF-код (800)
    - all_same_digits — все цифры одинаковые
    """
    if not phone or not isinstance(phone, str):
        return False, "empty"

    digits = re.sub(r"\D", "", phone)

    if len(digits) != 11:
        return False, f"wrong_length:{len(digits)}"

    if not digits.startswith("7"):
        return False, "wrong_prefix"

    def_code = digits[1:4]

    if def_code in INVALID_DEF_CODES:
        return False, f"invalid_def:{def_code}"

    if def_code in SUSPICIOUS_DEF_CODES:
        return False, f"suspicious_def:{def_code}"

    # Все цифры одинаковые
    if len(set(digits)) <= 2:
        return False, "all_same_digits"

    return True, "ok"


def get_company_domain(website: str) -> str | None:
    """Извлекает домен из website для сравнения с email."""
    if not website:
        return None
    try:
        parsed = urlparse(website if "://" in website else f"https://{website}")
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain if domain and "." in domain else None
    except Exception:
        return None


def email_matches_domain(email: str, domain: str) -> bool:
    """Проверяет, что email на домене компании (или поддомене)."""
    if not email or not domain:
        return False
    email_domain = email.rsplit("@", 1)[-1].lower()
    return email_domain == domain or email_domain.endswith("." + domain)


# ── Анализатор БД ─────────────────────────────────────────────────────────────


def validate_database(db_path: str, fix: bool = False) -> dict:
    """Анализирует и опционально исправляет все таблицы.

    Возвращает dict с протоколом изменений.
    """
    if not os.path.exists(db_path):
        print(f"ОШИБКА: База данных не найдена: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    report = {
        "timestamp": datetime.now().isoformat(),
        "db_path": db_path,
        "tables_checked": [],
        "summary": {},
        "details": [],
    }

    for table_name in ["raw_companies", "companies", "enriched_companies"]:
        table_report = validate_table(conn, table_name, fix)
        report["tables_checked"].append(table_name)
        report["details"].append(table_report)

    # Агрегированная статистика
    total_emails_removed = sum(t["emails_removed"] for t in report["details"])
    total_phones_removed = sum(t["phones_removed"] for t in report["details"])
    total_companies_flagged = sum(t["companies_flagged"] for t in report["details"])

    report["summary"] = {
        "total_emails_removed": total_emails_removed,
        "total_phones_removed": total_phones_removed,
        "total_companies_flagged": total_companies_flagged,
    }

    conn.close()

    return report


def validate_table(conn: sqlite3.Connection, table: str, fix: bool) -> dict:
    """Валидирует одну таблицу."""
    report = {
        "table": table,
        "total_rows": 0,
        "companies_flagged": 0,
        "emails_removed": 0,
        "phones_removed": 0,
        "emails_invalid": Counter(),
        "phones_invalid": Counter(),
        "domain_mismatches": 0,
        "over_limit_emails": 0,
        "over_limit_phones": 0,
        "fixes_applied": [] if fix else None,
    }

    # Определяем колонки
    email_col = "emails"
    phone_col = "phones"
    website_col = "website" if table != "enriched_companies" else "website"
    id_col = "id" if table != "enriched_companies" else "id"
    name_col = "name_best" if table == "companies" else "name"

    try:
        rows = conn.execute(
            f"SELECT {id_col}, {name_col}, {email_col}, {phone_col}, {website_col} "
            f"FROM {table}"
        ).fetchall()
    except sqlite3.OperationalError as e:
        print(f"  Таблица {table} не найдена или ошибка: {e}")
        return report

    report["total_rows"] = len(rows)
    if not rows:
        return report

    updates = []

    for row in rows:
        row_id = row[id_col]
        name = row[name_col] or "N/A"
        emails = json.loads(row[email_col]) if row[email_col] else []
        phones = json.loads(row[phone_col]) if row[phone_col] else []
        website = row[website_col]
        company_domain = get_company_domain(website)

        dirty = False
        row_issues = []

        # ── Валидация email ──
        clean_emails = []
        email_reasons = Counter()
        for em in emails:
            if not isinstance(em, str):
                email_reasons["not_string"] += 1
                continue
            em = em.strip()
            if not em:
                continue
            valid, reason = validate_email(em)
            if valid:
                clean_emails.append(em)
            else:
                email_reasons[reason] += 1
                report["emails_invalid"][reason] += 1
                row_issues.append(f"email:{em} → {reason}")

        # ── Приоритизация email: company domain > free provider > остальное ──
        if company_domain:
            # Помечаем email с чужого домена как подозрительные
            for em in list(clean_emails):
                if not email_matches_domain(em, company_domain):
                    em_domain = em.rsplit("@", 1)[-1].lower()
                    if em_domain not in FREE_EMAIL_DOMAINS:
                        # Email на домене, который не company domain и не free provider
                        # Скорее всего мусор, но не удаляем — только помечаем
                        report["domain_mismatches"] += 1

            # Сортируем: company domain первыми, free provider последними
            def email_priority(em: str) -> int:
                if email_matches_domain(em, company_domain):
                    return 0  # свой домен — приоритет
                em_dom = em.rsplit("@", 1)[-1].lower()
                if em_dom in FREE_EMAIL_DOMAINS:
                    return 2  # free provider — низкий приоритет
                return 1  # остальное

            clean_emails.sort(key=email_priority)

        # Лимит email
        if len(clean_emails) > MAX_EMAILS:
            report["over_limit_emails"] += 1
            cut = clean_emails[MAX_EMAILS:]
            clean_emails = clean_emails[:MAX_EMAILS]
            row_issues.append(f"email_limit: {MAX_EMAILS}, cut {len(cut)}: {cut}")

        # ── Валидация телефонов ──
        clean_phones = []
        phone_reasons = Counter()
        for ph in phones:
            if not isinstance(ph, str):
                phone_reasons["not_string"] += 1
                continue
            ph = ph.strip()
            if not ph:
                continue
            valid, reason = validate_phone(ph)
            if valid:
                clean_phones.append(ph)
            else:
                phone_reasons[reason] += 1
                report["phones_invalid"][reason] += 1
                row_issues.append(f"phone:{ph} → {reason}")

        # Дедуп телефонов (нормализация)
        seen_phones = set()
        deduped_phones = []
        for ph in clean_phones:
            digits = re.sub(r"\D", "", ph)
            if digits not in seen_phones:
                seen_phones.add(digits)
                deduped_phones.append(ph)
        if len(deduped_phones) != len(clean_phones):
            dup_count = len(clean_phones) - len(deduped_phones)
            row_issues.append(f"phone_dedup: removed {dup_count} duplicates")
            clean_phones = deduped_phones

        # Лимит телефонов
        if len(clean_phones) > MAX_PHONES:
            report["over_limit_phones"] += 1
            cut = clean_phones[MAX_PHONES:]
            clean_phones = clean_phones[:MAX_PHONES]
            row_issues.append(f"phone_limit: {MAX_PHONES}, cut {len(cut)}: {cut}")

        # ── Собираем изменения ──
        emails_removed = len(emails) - len([e for e in clean_emails if e])
        phones_removed = len(phones) - len(clean_phones)

        if emails_removed > 0 or phones_removed > 0:
            report["emails_removed"] += emails_removed
            report["phones_removed"] += phones_removed
            report["companies_flagged"] += 1
            dirty = True

        if dirty:
            update = {
                "row_id": row_id,
                "name": name,
                "table": table,
                "emails_before": emails,
                "emails_after": clean_emails,
                "phones_before": phones,
                "phones_after": clean_phones,
                "issues": row_issues,
            }
            if fix:
                updates.append(update)

    # Применяем исправления
    if fix and updates:
        cursor = conn.cursor()
        for upd in updates:
            cursor.execute(
                f"UPDATE {table} SET {email_col} = ?, {phone_col} = ? WHERE {id_col} = ?",
                (json.dumps(upd["emails_after"], ensure_ascii=False),
                 json.dumps(upd["phones_after"], ensure_ascii=False),
                 upd["row_id"])
            )
            report["fixes_applied"].append({
                "row_id": upd["row_id"],
                "name": upd["name"],
                "issues": upd["issues"],
            })
        conn.commit()
        print(f"  {table}: применено {len(updates)} исправлений")

    return report


# ── Конфликты дедупликации ────────────────────────────────────────────────────


def check_dedup_conflicts(db_path: str) -> dict:
    """Находит компании с needs_review=True и анализирует конфликты."""
    if not os.path.exists(db_path):
        return {"error": "DB not found", "conflicts": [], "total": 0}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT id, name_best, phones, emails, website, address, "
        "city, needs_review, review_reason, merged_from "
        "FROM companies WHERE needs_review = 1"
    ).fetchall()

    conflicts = []
    for row in rows:
        phones = json.loads(row["phones"]) if row["phones"] else []
        emails = json.loads(row["emails"]) if row["emails"] else []
        conflicts.append({
            "id": row["id"],
            "name": row["name_best"],
            "city": row["city"],
            "phones_count": len(phones),
            "emails_count": len(emails),
            "reason": row["review_reason"],
            "address": row["address"],
            "website": row["website"],
            "merged_from": json.loads(row["merged_from"]) if row["merged_from"] else [],
            "flag": "",
        })

    # Флаги: подозрительные кластеры
    for c in conflicts:
        flags = []
        if c["phones_count"] > MAX_PHONES:
            flags.append(f"too_many_phones({c['phones_count']})")
        if c["emails_count"] > MAX_EMAILS:
            flags.append(f"too_many_emails({c['emails_count']})")
        if "different_names" in c["reason"]:
            flags.append("different_names_in_cluster")
        if "different_cities" in c["reason"]:
            flags.append("different_cities_in_cluster")
        c["flag"] = " | ".join(flags) if flags else "review"

    conn.close()
    return {"total": len(conflicts), "conflicts": conflicts}


# ── Вывод отчёта ──────────────────────────────────────────────────────────────


def print_report(report: dict, conflicts: dict):
    """Красивый вывод отчёта в консоль."""
    print("\n" + "=" * 70)
    print("  ВАЛИДАЦИЯ БАЗЫ ДАННЫХ GRANITE CRM")
    print("=" * 70)
    print(f"  База: {report['db_path']}")
    print(f"  Время: {report['timestamp']}")
    print()

    s = report["summary"]
    print(f"  УДАЛЕНО: {s['total_emails_removed']} email, {s['total_phones_removed']} телефонов")
    print(f"  КОМПАНИЙ С ИЗМЕНЕНИЯМИ: {s['total_companies_flagged']}")
    print()

    for td in report["details"]:
        table = td["table"]
        print(f"  ── {table} ({td['total_rows']} записей) ──")
        print(f"     Удалено email: {td['emails_removed']}, телефонов: {td['phones_removed']}")
        print(f"     Компания с изменениями: {td['companies_flagged']}")

        if td["emails_invalid"]:
            print(f"     Причины удаления email:")
            for reason, count in td["emails_invalid"].most_common(10):
                print(f"       {reason}: {count}")

        if td["phones_invalid"]:
            print(f"     Причины удаления телефонов:")
            for reason, count in td["phones_invalid"].most_common(10):
                print(f"       {reason}: {count}")

        if td["domain_mismatches"]:
            print(f"     Email с чужого домена (не удалены): {td['domain_mismatches']}")
        if td["over_limit_emails"]:
            print(f"     Обрезка email >{MAX_EMAILS}: {td['over_limit_emails']} компаний")
        if td["over_limit_phones"]:
            print(f"     Обрезка телефонов >{MAX_PHONES}: {td['over_limit_phones']} компаний")

        if td["fixes_applied"] is not None:
            print(f"     Исправлений применено: {len(td['fixes_applied'])}")
        print()

    # Конфликты дедупликации
    print(f"  ── КОНФЛИКТЫ ДЕДУПЛИКАЦИИ ──")
    print(f"     Всего: {conflicts['total']}")
    if conflicts["conflicts"]:
        # Группируем по причине
        reason_counts = Counter(c["reason"] for c in conflicts["conflicts"])
        for reason, count in reason_counts.most_common():
            print(f"       {reason}: {count}")
        print()
        print("     Подозрительные (нужно проверить вручную):")
        suspicious = [c for c in conflicts["conflicts"] if "too_many" in c["flag"] or "different" in c["flag"]]
        for c in suspicious[:15]:  # первые 15
            print(f"       #{c['id']} {c['name'][:40]} ({c['city']}) "
                  f"— phones:{c['phones_count']} emails:{c['emails_count']} "
                  f"— [{c['reason']}]")
        if len(suspicious) > 15:
            print(f"       ... и ещё {len(suspicious) - 15}")
    print()

    print("=" * 70)
    print("  ГОТОВО")
    print("=" * 70)


def save_json_report(report: dict, conflicts: dict, output_path: str):
    """Сохраняет полный отчёт в JSON."""
    full_report = {
        **report,
        "dedup_conflicts": conflicts,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, ensure_ascii=False, indent=2)
    print(f"\n  JSON-отчёт сохранён: {output_path}")


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Валидация и очистка контактов в granite.db"
    )
    parser.add_argument(
        "--db", default=DEFAULT_DB_PATH,
        help="Путь к базе данных (default: data/granite.db)"
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="Применить исправления (без флага — только отчёт)"
    )
    parser.add_argument(
        "--json", default=None, metavar="FILE",
        help="Сохранить отчёт в JSON-файл"
    )
    parser.add_argument(
        "--conflicts-only", action="store_true",
        help="Только проверить конфликты дедупликации"
    )
    args = parser.parse_args()

    # Нормализация пути
    db_path = os.path.abspath(args.db)

    if not os.path.exists(db_path):
        print(f"ОШИБКА: База данных не найдена: {db_path}")
        print(f"Убедитесь, что скрепинг завершён и файл существует.")
        sys.exit(1)

    if args.conflicts_only:
        conflicts = check_dedup_conflicts(db_path)
        print(f"\nКонфликты дедупликации: {conflicts['total']}")
        for c in conflicts["conflicts"]:
            print(f"  #{c['id']} {c['name'][:50]} | {c['city']} | "
                  f"phones:{c['phones_count']} emails:{c['emails_count']} | "
                  f"[{c['reason']}]")
        return

    print(f"База данных: {db_path}")
    print(f"Режим: {'ИСПРАВЛЕНИЕ' if args.fix else 'ТОЛЬКО ОТЧЁТ (без изменений)'}")
    print()

    report = validate_database(db_path, fix=args.fix)
    conflicts = check_dedup_conflicts(db_path)
    print_report(report, conflicts)

    if args.json:
        save_json_report(report, conflicts, args.json)


if __name__ == "__main__":
    main()
