#!/usr/bin/env python3
"""
Funeral Agency Scraper v2 - Fast Version
Сбор + поиск Telegram (оптимизировано)
"""
import requests
from bs4 import BeautifulSoup
import json
import re
import os
import time
from datetime import datetime

OUTPUT = "output"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

TRANSLIT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh',
    'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
    'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'ts',
    'ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'
}

def normalize_phone(p):
    if not p: return ""
    d = re.sub(r"\D", "", p)
    if d.startswith("8"): d = "7" + d[1:]
    elif len(d) == 10: d = "7" + d
    return d if len(d) == 11 else ""

def check_tg(username):
    """Быстрая проверка Telegram"""
    username = username.lstrip('@').lower()
    if len(username) < 5: return None
    try:
        r = requests.get(f"https://t.me/{username}", headers=HEADERS, timeout=8)
        if "tgme_page_title" in r.text:
            m = re.search(r'tgme_page_description[^>]*>([^<]+)', r.text)
            desc = m.group(1).lower() if m else ""
            if any(k in desc for k in ['ритуал', 'похорон', 'памятник', 'мемориал', 'funeral']):
                return f"@{username}"
            m = re.search(r'tgme_page_title[^>]*>([^<]+)', r.text)
            title = m.group(1).lower() if m else ""
            if any(k in title for k in ['ритуал', 'memorial', 'angel', 'dom', 'pamyati']):
                return f"@{username}"
    except: pass
    return None

def find_telegram(name, phone=None):
    """Ищет Telegram по названию"""
    base = ''.join(TRANSLIT.get(c, c) for c in name.lower())
    base = re.sub(r'[^a-z0-9]', '', base)
    
    variants = [
        base[:30],
        base.replace('ritualnyeuslugi', 'ritual')[:30],
        f"{base[:20]}_ritual",
        f"ritual_{base[:20]}",
    ]
    
    if phone and len(phone) >= 11:
        variants.append(f"{base[:15]}{phone[-4:]}")
    
    for v in variants[:6]:
        if len(v) >= 5:
            tg = check_tg(v)
            if tg:
                return tg
            time.sleep(0.15)
    return None

def scrape_jsprav(city):
    """Сбор из JSprav"""
    print(f"\n🌐 JSprav.ru")
    companies = []
    seen = set()
    subdomain = {"astrakhan":"astrahan","moscow":"moskva1","spb":"sankt-peterburg1"}.get(city.lower(), city.lower())
    
    for cat in ["ritualnyie-uslugi", "ritualnyie-prinadlezhnosti-i-izgotovlenie-venkov"]:
        url = f"https://{subdomain}.jsprav.ru/{cat}/"
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            soup = BeautifulSoup(r.text, 'html.parser')
            
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    data = json.loads(script.string)
                    if data.get('@type') != 'ItemList': continue
                    
                    for item in data.get('itemListElement', []):
                        c = item.get('item', {})
                        if c.get('@type') != 'LocalBusiness': continue
                        
                        name = c.get('name', '')
                        if not name or name.lower() in seen: continue
                        seen.add(name.lower())
                        
                        addr = c.get('address', {})
                        same = c.get('sameAs', [])
                        
                        companies.append({
                            "name": name,
                            "phones": list(dict.fromkeys(normalize_phone(p) for p in c.get('telephone', []) if normalize_phone(p))),
                            "address": f"{addr.get('streetAddress', '')}, {addr.get('addressLocality', '')}",
                            "website": same[0] if same else "",
                            "lat": c.get('geo', {}).get('latitude'),
                            "lon": c.get('geo', {}).get('longitude'),
                        })
                except: continue
            time.sleep(0.5)
        except Exception as e:
            print(f"  ❌ {cat}: {e}")
    
    print(f"  ✅ {len(companies)} компаний")
    return companies

def find_all_telegrams(companies):
    """Поиск Telegram для всех"""
    print(f"\n🔍 Поиск Telegram")
    found = 0
    for i, c in enumerate(companies):
        if (i+1) % 5 == 0:
            print(f"  📊 {i+1}/{len(companies)}")
        phones_list = c.get('phones', []) or [None]
        tg = find_telegram(c['name'], phones_list[0])
        if tg:
            c['telegram'] = tg
            print(f"    ✅ {c['name'][:30]}: {tg}")
            found += 1
    print(f"\n  📊 С Telegram: {found}/{len(companies)}")
    return companies

def save(companies, city):
    city_dir = os.path.join(OUTPUT, city.lower())
    os.makedirs(city_dir, exist_ok=True)
    
    with_tg = [c for c in companies if c.get('telegram')]
    without_tg = [c for c in companies if not c.get('telegram')]
    
    with open(f"{city_dir}/all_companies.json", "w", encoding="utf-8") as f:
        json.dump(companies, f, ensure_ascii=False, indent=2)
    
    import csv
    fields = ["name", "phones", "telegram", "website", "address"]
    
    for data, fn in [(with_tg, "with_telegram.csv"), (without_tg, "without_telegram.csv")]:
        with open(f"{city_dir}/{fn}", "w", newline='', encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            w.writeheader()
            for c in data:
                c = c.copy()
                c['phones'] = '; '.join(c.get('phones', []))
                w.writerow(c)
    
    print(f"\n💾 {city_dir}/")
    print(f"   with_telegram.csv ({len(with_tg)})")
    print(f"   without_telegram.csv ({len(without_tg)})")

def main(city):
    print(f"\n{'='*50}")
    print(f"🔍 {city.upper()}")
    print(f"{'='*50}")
    companies = scrape_jsprav(city)
    companies = find_all_telegrams(companies)
    save(companies, city)
    print(f"\n✅ ГОТОВО")

if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "astrakhan")
