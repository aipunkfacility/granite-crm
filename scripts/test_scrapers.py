
import yaml
import sys
import os

# Добавляем корень проекта в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from granite.database import Database
from granite.scrapers.jsprav import JspravScraper
from granite.scrapers.dgis import DgisScraper
from granite.scrapers.yell import YellScraper
from granite.scrapers.firmsru import FirmsruScraper
from granite.scrapers.jsprav_playwright import JspravPlaywrightScraper
from granite.scrapers.firecrawl import FirecrawlScraper
from granite.scrapers._playwright import playwright_session
from loguru import logger

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def test_scraper(scraper_class, config, city, db=None, page=None):
    logger.info(f"--- Тестирование {scraper_class.__name__} ---")
    try:
        if db:
            scraper = scraper_class(config, city, db)
        elif page:
            scraper = scraper_class(config, city, page)
        else:
            scraper = scraper_class(config, city)
            
        # Ограничиваем количество страниц/результатов для теста, если возможно
        # Но у нас нет такого параметра в конструкторе, скреперы сами решают сколько парсить.
        # Просто запустим и посмотрим на первые результаты.
        results = scraper.run()
        logger.success(f"{scraper_class.__name__}: Найдено {len(results)} компаний")
        if results:
            logger.info(f"Пример первой компании: {results[0].name} ({results[0].website or 'нет сайта'})")
        return True
    except Exception as e:
        logger.error(f"Ошибка в {scraper_class.__name__}: {e}")
        return False

def main():
    config = load_config()
    db = Database(config["database"]["path"])
    city = "Астрахань" # Используем Астрахань для теста

    # 1. Быстрые скреперы
    test_scraper(JspravScraper, config, city)
    
    # Firecrawl может требовать npx и быть медленным, тестируем отдельно
    # test_scraper(FirecrawlScraper, config, city, db=db)

    # 2. Playwright скреперы
    logger.info("Запуск Playwright сессии для тестов...")
    with playwright_session(headless=True) as (browser, page):
        if page:
            test_scraper(DgisScraper, config, city, page=page)
            test_scraper(YellScraper, config, city, page=page)
            test_scraper(FirmsruScraper, config, city, page=page)
            test_scraper(JspravPlaywrightScraper, config, city, page=page)
        else:
            logger.error("Не удалось запустить Playwright")

if __name__ == "__main__":
    main()
