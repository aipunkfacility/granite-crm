# dedup/validator.py
import re
import requests
from granite.utils import normalize_phone, check_site_alive
from loguru import logger


def validate_phone(phone: str) -> bool:
    """Проверка что телефон валиден: 11 цифр, начинается с 7."""
    if not phone:
        return False
    digits = re.sub(r"\D", "", phone)
    return digits.startswith("7") and len(digits) == 11


def validate_phones(phones: list[str]) -> list[str]:
    """Оставляем только валидные и нормализованные номера."""
    result = []
    for p in phones:
        norm = normalize_phone(p)
        if norm and validate_phone(norm):
            result.append(norm)
    # Дедупликация с сохранением порядка
    seen: set = set()
    unique = []
    for p in result:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def validate_website(url: str) -> tuple[str | None, int | None]:
    """HEAD-запрос к сайту. Возвращает (url, status_code).

    Если сайт мёртв — возвращает (url, None).
    Нормализует URL: добавляет https:// если нет схемы.
    """
    if not url or url.strip() in ("", "-", "N/A"):
        return None, None

    url = url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"

    # Убираем мусор который иногда прилетает из скреперов
    if " " in url or "\n" in url:
        url = url.split()[0]

    status = check_site_alive(url)
    if status is None:
        logger.debug(f"  Site unreachable: {url}")
    return url, status


def validate_email(email: str) -> bool:
    """Базовая валидация email по регулярке."""
    if not email:
        return False
    pattern = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
    return bool(pattern.match(email.strip()))


def validate_emails(emails: list[str]) -> list[str]:
    """Фильтрация валидных email с дедупликацией."""
    return list(dict.fromkeys(e for e in emails if validate_email(e)))
