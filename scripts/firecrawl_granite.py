"""
Firecrawl Scraper для гранитных мастерских
Сбор базы производителей памятников по городам России
"""

import subprocess
import json
import csv
import re
import os
import sys

CITIES_DIR = os.path.join(os.path.dirname(__file__), "..", "cities")

# Поисковые запросы для гранитных мастерских
SEARCH_QUERIES = [
    "гранитная мастерская памятники",
    "производство памятников гранит",
    "мастерская по изготовлению памятников",
    "гранит памятники надгробия",
    "изготовление памятников из гранита",
]


def run_firecrawl_command(args: list) -> str:
    """Запускает команду firecrawl CLI"""
    cmd = ["npx", "-y", "firecrawl-cli@latest"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return result.stdout + result.stderr


def search_companies(city: str, limit: int = 10) -> list:
    """
    Поиск гранитных мастерских в городе
    """
    companies = []

    for query in SEARCH_QUERIES:
        search_query = f"{query} {city}"
        print(f"  Поиск: {search_query}")

        # Запускаем поиск
        output = run_firecrawl_command(["search", search_query, "--limit", str(limit)])

        # Парсим результаты
        # Формат: Название\nURL: ...
        lines = output.split("\n")
        current_company = {}

        for line in lines:
            line = line.strip()

            # Название компании (первая строка без URL)
            if line and not line.startswith("URL:") and "http" not in line:
                if len(line) > 3 and not line.startswith("["):
                    current_company["name"] = line

            # URL
            if line.startswith("URL:"):
                url = line.replace("URL:", "").strip()
                if url:
                    current_company["url"] = url

            # Описание (все между названием и URL)
            if "URL:" in line:
                desc_line = line.split("URL:")[0].strip()
                if desc_line and len(desc_line) > 10:
                    current_company["description"] = desc_line

            # Сохраняем компанию если есть URL
            if current_company.get("url") and current_company.get("name"):
                # Проверяем что это не дубликат
                if not any(c.get("url") == current_company["url"] for c in companies):
                    current_company["city"] = city
                    current_company["query"] = search_query
                    companies.append(current_company.copy())
                current_company = {}

    return companies


def scrape_company_details(url: str) -> dict:
    """
    Получение детальной информации о компании
    """
    print(f"    Scrape: {url}")

    output = run_firecrawl_command(["scrape", url, "--format", "markdown"])

    data = {
        "raw": output,
        "phones": [],
        "emails": [],
        "addresses": [],
        "telegram": None,
        "whatsapp": None,
    }

    # Извлечение телефонов
    phones = re.findall(
        r"(\+?7[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2})", output
    )
    data["phones"] = list(set(phones))

    # Извлечение email
    emails = re.findall(
        r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", output, re.IGNORECASE
    )
    data["emails"] = list(set(emails))

    # Извлечение адресов (простой поиск)
    address_patterns = [
        r"г\.?\s+[А-Яа-яё]+\s*,?\s*ул\.?\s+[А-Яа-яё]+",
        r"г\.?\s+[А-Яа-яё]+\s*,?\s*[А-Яа-яё]+\s+\d+",
        r"[А-Яа-яё]+\s+область.*ул\.?",
    ]
    for pattern in address_patterns:
        matches = re.findall(pattern, output)
        data["addresses"].extend(matches)

    # Поиск Telegram
    tg_matches = re.findall(r"(t\.me/[a-zA-Z0-9_]+|@[a-zA-Z0-9_]+)", output)
    if tg_matches:
        data["telegram"] = tg_matches[0]

    # Поиск WhatsApp
    wa_matches = re.findall(r"(wa\.me/[+]?7\d{10}|whatsapp\.com.*\+7\d{10})", output)
    if wa_matches:
        # Извлекаем номер телефона
        wa_phones = re.findall(r"\+?7(\d{10})", wa_matches[0])
        if wa_phones:
            data["whatsapp"] = f"https://wa.me/7{wa_phones[0]}"

    return data


def scrape_city(city: str):
    """
    Основная функция сбора для города
    """
    print(f"\n=== Сбор гранитных мастерских: {city} ===\n")

    # 1. Поиск компаний
    print(f"Этап 1: Поиск компаний...")
    companies = search_companies(city, limit=5)
    print(f"  Найдено: {len(companies)} компаний")

    # 2. Детальный сбор (только первые 10 для экономии)
    print(f"\nЭтап 2: Детальный сбор...")
    for i, company in enumerate(companies[:10]):
        print(f"  [{i + 1}/{min(10, len(companies))}] {company.get('name', 'Unknown')}")
        details = scrape_company_details(company["url"])
        company.update(details)

    # 3. Сохранение
    city_dir = os.path.join(CITIES_DIR, city.lower())
    os.makedirs(city_dir, exist_ok=True)

    # CSV (формат как в rostov_enriched.csv)
    csv_file = os.path.join(city_dir, "granite_companies.csv")
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=",")
        # Заголовки
        writer.writerow(
            [
                "ID",
                "Название",
                "Город",
                "Телефон",
                "Email",
                "Сайт",
                "Адрес",
                "VK",
                "Telegram",
                "WhatsApp",
                "Статус",
            ]
        )

        for i, company in enumerate(companies, start=1):
            phones = ", ".join(company.get("phones", []))
            emails = ", ".join(company.get("emails", []))
            telegram = company.get("telegram", "")
            whatsapp = company.get("whatsapp", "")
            addresses = company.get("addresses", [""])[0]
            url = company.get("url", "")

            writer.writerow(
                [
                    f"CMP{i:04d}",
                    company.get("name", ""),
                    city,
                    phones,
                    emails,
                    url,
                    addresses,
                    "",  # VK
                    telegram,
                    whatsapp,
                    "active",
                ]
            )
    print(f"\nСохранено: {csv_file}")

    # Markdown
    md_file = os.path.join(city_dir, "granite_companies.md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(f"# Гранитные мастерские — {city}\n\n")
        f.write(f"**Дата сбора:** 2026-03-30\n")
        f.write(f"**Всего:** {len(companies)} компаний\n\n")
        f.write("---\n\n")

        for i, company in enumerate(companies, 1):
            f.write(f"## {i}. {company.get('name', 'Unknown')}\n\n")

            url = company.get("url", "")
            if url:
                f.write(f"**Сайт:** {url}\n")

            phones = company.get("phones", [])
            if phones:
                f.write(f"**Телефоны:** {', '.join(phones)}\n")

            emails = company.get("emails", [])
            if emails:
                f.write(f"**Email:** {', '.join(emails)}\n")

            telegram = company.get("telegram")
            if telegram:
                f.write(f"**Telegram:** https://{telegram}\n")

            addresses = company.get("addresses", [])
            if addresses:
                f.write(f"**Адрес:** {addresses[0]}\n")

            f.write(f"**Источник поиска:** {company.get('query', '')}\n")
            f.write("\n---\n\n")

    print(f"Сохранено: {md_file}")

    return companies


def scrape_all_cities(cities: list):
    """
    Сбор по всем городам
    """
    for city in cities:
        scrape_city(city)
        print(f"\nПауза перед следующим городом...")
        import time

        time.sleep(2)  # rate limiting


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Тест на одном городе
        scrape_city("Москва")
    else:
        city = sys.argv[1]
        scrape_city(city)
