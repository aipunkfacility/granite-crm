"""
Funeral Agency Scraper
Сбор базы ритуальных компаний по городам России
Источники: 2GIS + JSprav
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import os
import sys
from urllib.parse import urljoin, quote
import time

# Playwright для динамических страниц
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwright not installed")

# Конфигурация
CITIES_DIR = os.path.join(os.path.dirname(__file__), "..", "cities")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def normalize_phone(phone: str) -> str:
    """Нормализует телефон к формату +7XXXXXXXXXX"""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("7"):
        digits = "7" + digits[1:]
    elif digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    return digits


def extract_phones(text: str) -> list:
    """Извлекает все телефоны из текста"""
    if not text:
        return []
    phones = re.findall(r"(\+?7[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2})", text)
    return list(set([normalize_phone(p) for p in phones if normalize_phone(p)]))


def extract_email(text: str) -> str | None:
    """Извлекает email из текста"""
    if not text:
        return None
    emails = re.findall(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", text, re.IGNORECASE)
    return emails[0] if emails else None


def scrape_2gis(city: str) -> list:
    """Парсит 2GIS через Playwright"""
    companies = []
    
    if not PLAYWRIGHT_AVAILABLE:
        print("  Playwright not available for 2GIS")
        return companies
    
    url = f"https://{city}.2gis.ru/search/{quote('ритуальные услуги')}"
    print(f"  Scraping 2GIS: {url}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=20000)
            
            # Scroll to load more
            for _ in range(3):
                page.evaluate("window.scrollBy(0, 1000)")
                time.sleep(1)
            
            # Find company cards - 2GIS uses various selectors
            cards = page.query_selector_all("div[class*='card'], div[class*='firm'], a[href*='/firm/']")
            
            for card in cards:
                try:
                    # Try to get name from link
                    name_elem = card.query_selector("div[class*='name'], a[class*='name'], span[class*='title']")
                    if not name_elem:
                        continue
                    name = name_elem.inner_text().strip()
                    if not name or len(name) < 3:
                        continue
                    
                    # Get link to full card
                    link = card.query_selector("a[href*='/firm/']")
                    if link:
                        href = link.get_attribute("href")
                    
                    # Get address
                    addr_elem = card.query_selector("div[class*='address'], span[class*='address']")
                    address = addr_elem.inner_text().strip() if addr_elem else ""
                    
                    # Get phone
                    phone_elem = card.query_selector("div[class*='phone'], span[class*='phone']")
                    phone_text = phone_elem.inner_text() if phone_elem else ""
                    phones = extract_phones(phone_text)
                    
                    if name:
                        companies.append({
                            "name": name,
                            "phones": phones,
                            "address": address,
                            "website": "",
                            "source": "2gis"
                        })
                except Exception as e:
                    continue
            
            browser.close()
            
    except Exception as e:
        print(f"  2GIS Playwright error: {e}")
    
    print(f"  Found: {len(companies)}")
    return companies


def scrape_yell(city: str) -> list:
    """Парсит Yell через Playwright"""
    companies = []
    
    if not PLAYWRIGHT_AVAILABLE:
        print("  Playwright not available for Yell")
        return companies
    
    url = f"https://{city}.yell.ru/catalog/ritualnye_uslugi/"
    print(f"  Scraping Yell: {url}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=20000)
            
            # Scroll to load more
            for _ in range(5):
                page.evaluate("window.scrollBy(0, 1000)")
                time.sleep(0.5)
            
            # Get company cards - Yell uses various selectors
            cards = page.query_selector_all("div.company-card, div.listing-item, a[href*='/company/']")
            
            for card in cards:
                try:
                    # Get name
                    name_elem = card.query_selector("h3 a, a.company-name, h2 a, span.company-name")
                    if not name_elem:
                        continue
                    name = name_elem.inner_text().strip()
                    if not name or len(name) < 3:
                        continue
                    
                    # Get address
                    addr_elem = card.query_selector("address, div.address, span.address")
                    address = addr_elem.inner_text().strip() if addr_elem else ""
                    
                    # Get phone
                    phone_elem = card.query_selector("span.phone, a.phone, div.phone")
                    phone_text = phone_elem.inner_text() if phone_elem else ""
                    phones = extract_phones(phone_text)
                    
                    # Get website
                    site_elem = card.query_selector("a.website-link, a[href*='http']:not([href*='yell'])")
                    website = site_elem.get_attribute("href") if site_elem else ""
                    
                    # Get email from page content if available
                    page_content = card.inner_html()
                    email = extract_email(page_content)
                    
                    if name:
                        companies.append({
                            "name": name,
                            "phones": phones,
                            "address": address,
                            "website": website,
                            "email": email,
                            "source": "yell"
                        })
                except:
                    continue
            
            browser.close()
            
    except Exception as e:
        print(f"  Yell Playwright error: {e}")
    
    print(f"  Found: {len(companies)}")
    return companies


def scrape_firmsru(city: str) -> list:
    """Парсит Firmsru через Playwright"""
    companies = []
    
    if not PLAYWRIGHT_AVAILABLE:
        print("  Playwright not available for Firmsru")
        return companies
    
    # Firmsru URL format
    url = f"https://firmsru.ru/{city}/ритуальные-услуги/"
    print(f"  Scraping Firmsru: {url}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=20000)
            
            # Scroll to load more
            for _ in range(5):
                page.evaluate("window.scrollBy(0, 1000)")
                time.sleep(0.5)
            
            # Get company items - Firmsru uses various selectors
            cards = page.query_selector_all("div.company, div.firm-item, a[href*='/firm/']")
            
            for card in cards:
                try:
                    # Get name
                    name_elem = card.query_selector("h3 a, h2 a, a.name, span.name")
                    if not name_elem:
                        continue
                    name = name_elem.inner_text().strip()
                    if not name or len(name) < 3:
                        continue
                    
                    # Get address
                    addr_elem = card.query_selector("address, div.address, span.address")
                    address = addr_elem.inner_text().strip() if addr_elem else ""
                    
                    # Get phone
                    phone_elems = card.query_selector_all("span.phone, div.phone, a[href^='tel:']")
                    phones = []
                    for p in phone_elems:
                        phone_text = p.inner_text()
                        phones.extend(extract_phones(phone_text))
                    
                    # Get website
                    site_elem = card.query_selector("a[href*='http']:not([href*='firmsru'])")
                    website = site_elem.get_attribute("href") if site_elem else ""
                    
                    # Get email from card content
                    page_content = card.inner_html()
                    email = extract_email(page_content)
                    
                    if name:
                        companies.append({
                            "name": name,
                            "phones": phones,
                            "address": address,
                            "website": website,
                            "email": email,
                            "source": "firmsru"
                        })
                except:
                    continue
            
            browser.close()
            
    except Exception as e:
        print(f"  Firmsru Playwright error: {e}")
    
    print(f"  Found: {len(companies)}")
    return companies


def scrape_jsprav(city: str) -> list:
    """Парсит JSprav через Playwright"""
    companies = []
    
    if not PLAYWRIGHT_AVAILABLE:
        print("  Playwright not available for JSprav")
        return companies
    
    # URL: astrahan.jsprav.ru/ritualnyie-uslugi/
    url = f"https://{city}.jsprav.ru/ritualnyie-uslugi/"
    print(f"  Scraping JSprav: {url}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=60000)
            import time
            time.sleep(3)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            
            # Scroll to load more
            for _ in range(5):
                page.evaluate("window.scrollBy(0, 1000)")
                time.sleep(0.5)
            
            # JSprav structure: links to company pages
            # Get all links that look like company links (contain company name)
            company_links = page.query_selector_all("a[href*='/ritual']")
            
            # Filter to get unique company URLs (not navigation)
            seen_urls = set()
            for link in company_links:  # No limit - collect all
                try:
                    href = link.get_attribute("href")
                    if not href or href in seen_urls:
                        continue
                    # Skip if it's just a category page
                    if href.endswith('/ritualnyie-uslugi/') or href.endswith('/ritualnyie-prinadlezhnosti/'):
                        continue
                    seen_urls.add(href)
                    
                    # Click on company link to get details
                    page.goto("https://" + city + ".jsprav.ru" + href, timeout=15000)
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    
                    # Get company name
                    title = page.query_selector("h1")
                    name = title.inner_text().strip() if title else ""
                    
                    # Get phones
                    phone_elems = page.query_selector_all("a[href^='tel:']")
                    phones = []
                    for p in phone_elems:
                        phone_text = p.inner_text()
                        phones.extend(extract_phones(phone_text))
                    
                    # Get address
                    addr_elem = page.query_selector("address")
                    address = addr_elem.inner_text().strip() if addr_elem else ""
                    
                    # Get website
                    site_elem = page.query_selector("a[href*='http']:not([href*='jsprav'])")
                    website = site_elem.get_attribute("href") if site_elem else ""
                    
                    # Get email - extract from page content
                    page_content = page.content()
                    email = extract_email(page_content)
                    
                    if name:
                        companies.append({
                            "name": name,
                            "phones": phones,
                            "address": address,
                            "website": website,
                            "email": email,
                            "source": "jsprav"
                        })
                    
                    # Go back to list
                    page.goto(url, timeout=15000)
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    
                except Exception as e:
                    continue
            
            browser.close()
            
    except Exception as e:
        print(f"  JSprav Playwright error: {e}")
    
    print(f"  Found: {len(companies)}")
    return companies


def merge_companies(companies: list) -> list:
    """
    Объединяет компании по телефону.
    Дубликаты не удаляются, а соединяются (дополняют друг друга).
    Компании без телефона сохраняются по имени.
    """
    phone_map = {}
    no_phone_map = {}  # Для компаний без телефона
    
    for company in companies:
        if not company.get("phones"):
            # Без телефона - сохраняем по имени
            key = company.get("name", "").lower().strip()
            if key and key not in no_phone_map:
                no_phone_map[key] = company
            continue
        
        primary_phone = company["phones"][0]
        
        if primary_phone not in phone_map:
            phone_map[primary_phone] = company
        else:
            # Объединяем поля
            existing = phone_map[primary_phone]
            
            # Объединяем телефоны
            all_phones = list(set(existing.get("phones", []) + company.get("phones", [])))
            existing["phones"] = all_phones
            
            # Объединяем адрес (если пустой - берем из нового)
            if not existing.get("address") and company.get("address"):
                existing["address"] = company["address"]
            
            # Объединяем сайт (если пустой - берем из нового)
            if not existing.get("website") and company.get("website"):
                existing["website"] = company["website"]
            
            # Объединяем email
            if not existing.get("email") and company.get("email"):
                existing["email"] = company["email"]
            
            # Добавляем источник
            sources = set(existing.get("source", "").split(",") + [company.get("source", "")])
            existing["source"] = ", ".join([s for s in sources if s])
    
    # Объединяем: с телефоном + без телефона
    return list(phone_map.values()) + list(no_phone_map.values())


def save_json(data: list, filepath: str):
    """Сохраняет в JSON"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {filepath}")


def save_markdown(companies: list, filepath: str):
    """Сохраняет в companies.md"""
    if not companies:
        print(f"No companies to save to {filepath}")
        return
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, "w", encoding="utf-8") as f:
        city_name = companies[0].get('city', 'Unknown')
        f.write(f"# Компании — {city_name}\n\n")
        f.write(f"**Дата сбора:** 2026-03-14\n")
        f.write(f"**Источники:** 2GIS, JSprav\n")
        f.write(f"**Всего:** {len(companies)} компаний\n\n")
        f.write("---\n\n")
        
        for i, company in enumerate(companies, 1):
            f.write(f"## {i}. {company.get('name', 'Unknown')}\n\n")
            
            phones = company.get("phones", [])
            if phones:
                f.write(f"**Телефон:** {', '.join(phones)}\n")
            else:
                f.write(f"**Телефон:** не указан\n")
            
            address = company.get("address", "")
            f.write(f"**Адрес:** {address if address else 'не указан'}\n")
            
            website = company.get("website", "")
            f.write(f"**Сайт:** {website if website else 'не указан'}\n")
            
            email = company.get("email", "")
            f.write(f"**Email:** {email if email else 'не указан'}\n")
            f.write(f"**Telegram:** не найден\n")
            f.write(f"**WhatsApp:** не указан\n")
            
            source = company.get("source", "")
            if source:
                f.write(f"**Источник:** {source}\n")
            
            f.write("\n---\n\n")
    
    print(f"Saved: {filepath}")


def scrape_city(city: str):
    """Основная функция сбора"""
    print(f"\n=== Scraping {city} ===\n")
    
    city_dir = os.path.join(CITIES_DIR, city.lower())
    os.makedirs(city_dir, exist_ok=True)
    
    raw_file = os.path.join(city_dir, "companies_raw.json")
    json_file = os.path.join(city_dir, "companies.json")
    md_file = os.path.join(city_dir, "companies.md")
    
    all_companies = []
    
    # 2GIS
    print("Scraping 2GIS...")
    companies = scrape_2gis(city)
    all_companies.extend(companies)
    
    # JSprav  
    print("Scraping JSprav...")
    companies = scrape_jsprav(city)
    all_companies.extend(companies)
    
    # Yell
    print("Scraping Yell...")
    companies = scrape_yell(city)
    all_companies.extend(companies)
    
    # Firmsru
    print("Scraping Firmsru...")
    companies = scrape_firmsru(city)
    all_companies.extend(companies)
    
    print(f"\nTotal before merge: {len(all_companies)}")
    
    # Сохраняем сырые данные
    save_json(all_companies, raw_file)
    
    # Объединение (merge) вместо дедупликации
    merged_companies = merge_companies(all_companies)
    
    # Добавляем city для markdown
    for c in merged_companies:
        c["city"] = city.capitalize()
    
    print(f"After merge: {len(merged_companies)}")
    
    # Сохраняем JSON
    save_json(merged_companies, json_file)
    
    # Сохраняем markdown
    save_markdown(merged_companies, md_file)
    
    print(f"\n=== Done: {len(merged_companies)} companies ===\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scrape_city.py <city>")
        print("Example: python scrape_city.py astrakhan")
        sys.exit(1)
    
    city = sys.argv[1].lower()
    scrape_city(city)
