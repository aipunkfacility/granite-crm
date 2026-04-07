# enrichers/tech_extractor.py
import re
from granite.utils import fetch_page
from loguru import logger

class TechExtractor:
    """Извлекает движок сайта (CMS) и наличие виджетов типа Marquiz."""

    def __init__(self, config: dict):
        pass  # config kept for API compatibility

    def extract(self, url: str) -> dict:
        result = {
            "cms": "unknown",
            "has_marquiz": False
        }
        
        if not url:
            return result
            
        try:
            html = fetch_page(url, timeout=10)
            if not html:
                return result
                
            # Проверка CMS (case-insensitive)
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
                
            # Проверка Marquiz (квизы очень популярны у интеграторов)
            if "marquiz.ru" in html:
                result["has_marquiz"] = True
                
        except Exception as e:
            logger.warning(f"Tech extractor error {url}: {e}")
            
        return result
