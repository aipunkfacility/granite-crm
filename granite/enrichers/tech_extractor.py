# enrichers/tech_extractor.py
import re
from granite.utils import fetch_page, is_safe_url
from granite.http_client import async_fetch_page
from loguru import logger

# D2-refactor: скомпилированные regex для <meta name="generator">
_META_GENERATOR_PATTERNS = [
    re.compile(
        r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']generator["\']',
        re.IGNORECASE,
    ),
]

# Маппинг: подстрока в content -> имя CMS
_CMS_GENERATOR_MAP = {
    "wordpress": "wordpress",
    "joomla": "joomla",
    "bitrix": "bitrix",
    "1c-bitrix": "bitrix",
    "tilda": "tilda",
    "modx": "modx",
    "drupal": "drupal",
}

# Паттерны CMS по подстрокам в HTML (до проверки meta generator)
_CMS_HTML_PATTERNS = [
    ("wordpress", ["wp-content", "wordpress"]),
    ("bitrix", ["bitrix", "1c-bitrix"]),
    ("tilda", ["tilda.ws", "tilda.cc", "created on tilda"]),
    ("flexbe", ["flexbe"]),
    ("lpmotor", ["lpmotor"]),
    ("joomla", ["joomla"]),
    ("opencart", ["opencart", "route=common/home"]),
]


class TechExtractor:
    """Извлекает движок сайта (CMS), виджеты и tech_keywords.

    AUDIT #8: tech_keywords из config.yaml теперь реально используются.
    Ключевые слова разбиты на 4 категории: equipment, production, portrait, site_constructor.
    Результат возвращается в поле ``tech_signals`` для использования в скоринге.
    """

    def __init__(self, config: dict):
        enrichment_cfg = config.get("enrichment", {})
        self.tech_keywords = enrichment_cfg.get("tech_keywords", {})
        # Компилируем regex для каждой категории для скорости
        self._compiled = {}
        for category, keywords in self.tech_keywords.items():
            if keywords:
                pattern = "|".join(re.escape(kw.lower()) for kw in keywords)
                self._compiled[category] = re.compile(pattern)

    def _scan_tech_signals(self, text: str) -> dict:
        """AUDIT #8: Сканирует текст на tech_keywords из config.yaml.

        Возвращает словарь {category: True} для найденных категорий.
        """
        signals = {}
        text_lower = text.lower()
        for category, pattern in self._compiled.items():
            if pattern.search(text_lower):
                signals[category] = True
        return signals

    def _detect_cms_and_widgets(self, html: str, html_lower: str, result: dict) -> None:
        """D2-refactor: общая логика детекции CMS и виджетов для sync/async.

        1. CMS по подстрокам в HTML (быстрая проверка)
        2. Виджет Marquiz
        3. CMS через <meta name="generator"> (fallback)
        """
        # 1. CMS по подстрокам в HTML (только если ещё не определён)
        if result["cms"] == "unknown":
            for cms_name, patterns in _CMS_HTML_PATTERNS:
                if any(p in html_lower for p in patterns):
                    result["cms"] = cms_name
                    break

        # 2. Marquiz
        if "marquiz.ru" in html_lower:
            result["has_marquiz"] = True

        # 3. CMS через <meta name="generator"> (если ещё не определён)
        if result["cms"] == "unknown":
            for pat in _META_GENERATOR_PATTERNS:
                m = pat.search(html)
                if m:
                    gen = m.group(1).lower()
                    for key, cms_name in _CMS_GENERATOR_MAP.items():
                        if key in gen:
                            result["cms"] = cms_name
                            break
                    break

    def extract(self, url: str) -> dict:
        result = {
            "cms": "unknown",
            "has_marquiz": False,
            "tech_signals": {},  # AUDIT #8
        }
        
        if not url:
            return result

        if not is_safe_url(url):
            return result
            
        try:
            html = fetch_page(url, timeout=10)
            if not html:
                return result
                
            html_lower = html.lower()
            self._detect_cms_and_widgets(html, html_lower, result)

            # AUDIT #8: Сканируем на tech_keywords
            if self._compiled:
                result["tech_signals"] = self._scan_tech_signals(html_lower)
                
        except Exception as e:
            logger.warning(f"Tech extractor error {url}: {e}")
            
        return result

    async def extract_async(self, url: str) -> dict:
        """Async версия extract — использует httpx.AsyncClient.

        Идентична по логике extract(), но неблокирующая.
        """
        result = {
            "cms": "unknown",
            "has_marquiz": False,
            "tech_signals": {},  # AUDIT #8
        }

        if not url:
            return result

        if not is_safe_url(url):
            return result

        try:
            html = await async_fetch_page(url, timeout=10)
            if not html:
                return result

            html_lower = html.lower()
            self._detect_cms_and_widgets(html, html_lower, result)

            # AUDIT #8: Сканируем на tech_keywords
            if self._compiled:
                result["tech_signals"] = self._scan_tech_signals(html_lower)

        except Exception as e:
            logger.warning(f"Tech extractor async error {url}: {e}")

        return result
