# enrichers/tg_trust.py
import requests
from bs4 import BeautifulSoup
from loguru import logger
from granite.utils import adaptive_delay, get_random_ua
from granite.enrichers.tg_finder import tg_request
from granite.enrichers._tg_common import TG_MAX_RETRIES, TG_INITIAL_BACKOFF


def check_tg_trust(url: str) -> dict:
    """Анализирует Telegram-профиль: живой ли это контакт."""
    if not url:
        return {"trust_score": 0}

    headers = {"User-Agent": get_random_ua()}

    result = {
        "has_avatar": False,
        "has_description": False,
        "is_bot": False,
        "is_channel": False,
        "trust_score": 0,
    }

    r = tg_request(url, headers)
    if not r:
        return result

    soup = BeautifulSoup(r.text, "html.parser")

    # Avatar: проверяем наличие изображения профиля
    if soup.select(".tgme_page_photo_image"):
        result["has_avatar"] = True
        result["trust_score"] += 1

    # Description: проверяем наличие блока описания
    if soup.select(".tgme_page_description"):
        result["has_description"] = True
        result["trust_score"] += 1

    # Channel: проверяем наличие информации о подписчиках
    extra = soup.select(".tgme_page_extra")
    if extra:
        extra_text = extra[0].get_text().lower()
        if "subscribers" in extra_text or "members" in extra_text:
            result["is_channel"] = True
            result["trust_score"] -= 1

    # Bot: проверяем класс бота
    if soup.select(".tgme_page_bot_button"):
        result["is_bot"] = True
        result["trust_score"] -= 1

    adaptive_delay(1.0, 2.0)
    return result
