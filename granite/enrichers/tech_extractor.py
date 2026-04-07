# enrichers/tech_extractor.py
import re
from granite.utils import fetch_page
from loguru import logger

class TechExtractor:
    """Извлекает движок сайта (CMS) и наличие виджетов типа Marquiz."""

    def __init__(self, config: dict):
        self.config = config
        
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
                
            # Проверка CMS
            if "wp-content" in html or "WordPress" in html:
                result["cms"] = "wordpress"
            elif "bitrix" in html or "1c-bitrix" in html:
                result["cms"] = "bitrix"
            elif "tilda.ws" in html or "tilda.cc" in html or "created on Tilda" in html:
                result["cms"] = "tilda"
            elif "flexbe" in html:
                result["cms"] = "flexbe"
            elif "lpmotor" in html:
                result["cms"] = "lpmotor"
            elif "Joomla" in html:
                result["cms"] = "joomla"
            elif "OpenCart" in html or "route=common/home" in html:
                result["cms"] = "opencart"
                
            # Проверка Marquiz (квизы очень популярны у интеграторов)
            if "marquiz.ru" in html:
                result["has_marquiz"] = True
                
        except Exception as e:
            logger.warning(f"Tech extractor error {url}: {e}")
            
        return result
