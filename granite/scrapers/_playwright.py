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


# Массив популярных viewport'ов для рандомизации
_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 720},
]


def _get_random_desktop_ua() -> str:
    """Случайный User-Agent из популярных десктопных браузеров.

    Не используется fake_useragent — он генерирует слишком экзотические UA,
    которые сами по себе являются сигнатурой ботов.
    """
    uas = [
        # Chrome 135 на Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        # Chrome 135 на macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        # Firefox 137 на Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
        # Edge 135 на Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
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
        _stealth_apply = None
        # playwright-stealth 1.0.x: экспортирует stealth_sync / stealth_async / StealthConfig
        # playwright-stealth < 1.0: экспортирует stealth / stealth_sync
        # Все варианты требуют setuptools (pkg_resources). Без него — ImportError.
        try:
            from playwright_stealth import stealth_sync
            _stealth_apply = stealth_sync
        except ImportError as e:
            # Отличаем «модуль не установлен» от «модуль сломался при импорте»
            # (например, нет pkg_resources/setuptools)
            try:
                import playwright_stealth  # noqa: F401
                logger.warning(
                    f"playwright-stealth установлен, но не импортируется: {e}. "
                    f"Возможно не хватает setuptools: pip install setuptools"
                )
            except ImportError:
                logger.warning("playwright-stealth не установлен, продолжаем без него "
                               "(pip install playwright-stealth)")
        _has_stealth = _stealth_apply is not None

        pw = sync_playwright().start()
        try:
            browser = pw.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                context = browser.new_context(
                    viewport=random.choice(_VIEWPORTS),
                    user_agent=_get_random_desktop_ua(),
                )
                context.set_default_timeout(30000)  # 30s — защитный дефолт
                try:
                    page = context.new_page()
                    if _stealth_apply:
                        try:
                            _stealth_apply(page)
                        except Exception:
                            # stealth не применился — пропускаем
                            logger.warning("playwright_stealth: не удалось применить stealth, продолжаем без него")
                    yield browser, page
                finally:
                    try:
                        context.close()
                    except Exception:
                        pass
            finally:
                try:
                    browser.close()
                except Exception:
                    pass
        finally:
            pw.stop()
else:
    @contextmanager
    def playwright_session(headless: bool = True):
        """FIX 4.7: Fail-fast вместо yield (None, None).

        Стуб_yield (None, None) заставляет callers обрабатывать оба None.
        ImportError позволяет отловить отсутствие Playwright выше по стеку.
        """
        raise ImportError(
            "Playwright не установлен. Установите: "
            "pip install playwright && playwright install chromium"
        )
