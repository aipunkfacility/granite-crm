import yaml
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from granite.database import Database
from granite.scrapers.dgis import DgisScraper
from granite.scrapers._playwright import playwright_session
from loguru import logger

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    config = load_config()
    db = Database(config["database"]["path"])
    city = "Астрахань"

    logger.info("Запуск Playwright сессии для тестов (headless=True)...")
    with playwright_session(headless=True) as (browser, page):
        if page:
            logger.info("DGIS scraper ...")
            scraper = DgisScraper(config, city, page)
            res = scraper.run()
            logger.info(f"Найдено: {len(res)}")
        else:
            logger.error("Не удалось запустить Playwright")

if __name__ == "__main__":
    main()
