# scrapers/_playwright.py
from contextlib import contextmanager
from loguru import logger
import random

try:
    from playwright.sync_api import sync_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright не установлен. Playwright-скреперы недоступны. "
                   "Установите: pip install playwright && playwright install chromium")


def _get_random_desktop_ua() -> str:
    """Случайный User-Agent из популярных десктопных браузеров.

    Не используется fake_useragent — он генерирует слишком экзотические UA,
    которые сами по себе являются сигнатурой ботов.
    """
    uas = [
        # Chrome на Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        # Chrome на macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        # Firefox на Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        # Edge на Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    ]
    return random.choice(uas)


if PLAYWRIGHT_AVAILABLE:
    @contextmanager
    def playwright_session(headless: bool = True):
        """Контекстный менеджер: один браузер на всю сессию.

        Использование:
            with playwright_session() as (browser, page):
                dgis = DgisScraper(config, city, playwright_page=page)
                yell = YellScraper(config, city, playwright_page=page)
                results_dgis = dgis.run()
                results_yell = yell.run()
        """
        try:
            from playwright_stealth import stealth_sync
            _has_stealth = True
        except ImportError:
            try:
                from playwright_stealth import stealth
                stealth_sync = stealth
                _has_stealth = True
            except ImportError:
                logger.warning("playwright-stealth не установлен, продолжаем без него "
                               "(pip install playwright-stealth)")
                _has_stealth = False

        pw = sync_playwright().start()
        browser = pw.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=_get_random_desktop_ua(),
        )
        page = context.new_page()
        if _has_stealth:
            try:
                stealth_sync(page)
            except TypeError:
                # Если stealth_sync это модуль, а не функция — пропускаем
                logger.warning("playwright_stealth: не удалось применить stealth, продолжаем без него")
        try:
            yield browser, page
        finally:
            context.close()
            browser.close()
            pw.stop()
else:
    @contextmanager
    def playwright_session(headless: bool = True):
        """Заглушка — Playwright не установлен."""
        logger.error("Playwright не установлен. playwright_session недоступен.")
        yield None, None
