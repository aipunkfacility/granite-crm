# enrichers/tech_extractor.py
import re
from granite.utils import fetch_page, is_safe_url
from granite.http_client import async_fetch_page
from loguru import logger

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
            if "wp-content" in html_lower or "wordpress" in html_lower:
                result["cms"] = "wordpress"
            elif "bitrix" in html_lower or "1c-bitrix" in html_lower:
                result["cms"] = "bitrix"
            elif "tilda.ws" in html_lower or "tilda.cc" in html_lower or "created on tilda" in html_lower:
                result["cms"] = "tilda"
            elif "flexbe" in html_lower:
                result["cms"] = "flexbe"
            elif "lpmotor" in html_lower:
                result["cms"] = "lpmotor"
            elif "joomla" in html_lower:
                result["cms"] = "joomla"
            elif "opencart" in html_lower or "route=common/home" in html_lower:
                result["cms"] = "opencart"
                
            if "marquiz.ru" in html_lower:
                result["has_marquiz"] = True

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
            if "wp-content" in html_lower or "wordpress" in html_lower:
                result["cms"] = "wordpress"
            elif "bitrix" in html_lower or "1c-bitrix" in html_lower:
                result["cms"] = "bitrix"
            elif "tilda.ws" in html_lower or "tilda.cc" in html_lower or "created on tilda" in html_lower:
                result["cms"] = "tilda"
            elif "flexbe" in html_lower:
                result["cms"] = "flexbe"
            elif "lpmotor" in html_lower:
                result["cms"] = "lpmotor"
            elif "joomla" in html_lower:
                result["cms"] = "joomla"
            elif "opencart" in html_lower or "route=common/home" in html_lower:
                result["cms"] = "opencart"

            if "marquiz.ru" in html_lower:
                result["has_marquiz"] = True

            # AUDIT #8: Сканируем на tech_keywords
            if self._compiled:
                result["tech_signals"] = self._scan_tech_signals(html_lower)

        except Exception as e:
            logger.warning(f"Tech extractor async error {url}: {e}")

        return result
