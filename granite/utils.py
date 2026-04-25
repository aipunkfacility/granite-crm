# utils.py
import re
import time
import random
from urllib.parse import urlparse
from rapidfuzz import fuzz


# ── SEO-title детектор (общий для merger.py и web_search.py) ─────────
# FIX: Улучшена обработка слипшихся слов (характерно для SEO-мусора без пробелов)
_SEO_TITLE_PATTERN = re.compile(
    r"(?:купить|цен[аыуе]|недорог|заказать|от производитель|"
    r"с установк|на могил|доставк|скидк|каталог|"
    r"памятник[аиы]?\s*(?:из|в|на|от|и)?\s*|"  # "Памятникииз", "Памятники в"
    r"изготовлен.*(?:памятник|надгробие|гранит)|"
    r"гранитн[ые]+\s*мастерск|"            # "Гранитные мастерские"
    r"памятники\s*(?:в|из|на|и)\s*|"       # "Памятники в/из"
    r"памятники\s*(?:на\s*кладбищ)|"       # "Памятники на кладбищ"
    r"изготовление\s*памятников|"          # "Изготовление памятников"
    r"памятники\s*и\s*надгробия|"          # "Памятники и надгробия"
    r"производство\s*памятников|"
    # B2: Новые паттерны для слипшихся слов (SEO-краулеры сливают слова)
    r"памятниковизгранита|памятникиизгранита|"
    r"изготовлениепамятников|установкапамятников|"
    r"памятникинамогилу|купитьпамятник|"
    r"заказатьпамятник|гранитнаямастерская)",
    re.IGNORECASE,
)


def is_seo_title(name: str) -> bool:
    """Проверяет, выглядит ли имя как SEO-заголовок, а не название компании.

    Используется в merger.py (при слиянии кластеров) и web_search.py
    (при фильтрации результатов поиска). Вынесено из web_search.py в utils.py
    чтобы избежать циклического импорта (dedup/ → scrapers/).
    """
    if not name:
        return True
    if len(name) > 100:  # Было 80, увеличил для длинных SEO-фраз
        return True
    if _SEO_TITLE_PATTERN.search(name):
        return True

    # B2: Детектор слипшихся кириллических слов (SEO-краулеры сливают слова)
    # Ищем паттерн: строчная кириллица сразу после строчной кириллицы без пробела,
    # и суммарная длина "склеенного" слова > 15 символов
    _concatenated = re.findall(r'[а-яё]{6,}', name.lower())
    if _concatenated and max(len(w) for w in _concatenated) > 15:
        return True

    # FIX: Детектор слов без пробелов (SEO-спам)
    # Если во всей строке нет пробела
    if len(name) > 25 and " " not in name:
        return True
        
    # FIX: Детектор слишком длинных "слов" (слипшиеся слова типа ПамятникиНаЗаказ)
    for word in name.split():
        if len(word) > 20 and not word.startswith("http"):
            return True

    # FIX: Если слишком много пробелов или нет букв (только спецсимволы)
    if len(re.findall(r"[а-яa-z]", name, re.I)) < 3:
        return True
    return False


def normalize_messenger_url(url: str, m_type: str = "telegram") -> str:
    """Очистка ссылок мессенджеров от двойных префиксов и мусора.
    Пример: https://t.me/https://t.me/user -> https://t.me/user
    """
    if not url or not isinstance(url, str):
        return ""
    
    # Паттерны для очистки
    tg_patterns = [r"https?://t\.me/", r"https?://telegram\.me/", r"tg://resolve\?domain="]
    wa_patterns = [r"https?://wa\.me/", r"https?://api\.whatsapp\.com/send\?phone=", r"https?://api\.whatsapp\.com/send/\?phone="]
    
    current = url.strip()
    
    if m_type in ("tg", "telegram"):
        pattern = "(?:" + "|".join(tg_patterns) + ")"
        prefix = "https://t.me/"
    elif m_type in ("wa", "whatsapp"):
        pattern = "(?:" + "|".join(wa_patterns) + ")"
        # Пользователь предпочитает длинный формат api.whatsapp.com
        prefix = "https://api.whatsapp.com/send?phone="
    else:
        return url

    # Рекурсивная очистка всех известных префиксов из начала строки
    while True:
        prev = current
        # Убираем все варианты префиксов из начала
        current = re.sub(r"^" + pattern, "", current, flags=re.I)
        current = current.lstrip("/@ ")
        if current == prev:
            break
            
    if not current:
        return ""
        
    # Для WhatsApp оставляем только цифры в "хвосте" ссылки
    if m_type in ("wa", "whatsapp"):
        # Убираем всё кроме цифр в ID (чтобы отсечь &text= и прочее, если было)
        current = re.sub(r"\D", "", current)
        if not current: return ""
        # Нормализация кода РФ (8 -> 7)
        if current.startswith("8") and len(current) == 11:
            current = "7" + current[1:]
        
    return prefix + current


# ── A-7: Детектор имен агрегаторов ──────────────────────────────────────────
# Список названий брендов-агрегаторов, которые ошибочно попадают в поле 'name'
_AGGREGATOR_NAMES = frozenset({
    "uslugio", "услугио", "zoon", "зун", "yell", "елл", "jsprav",
    "pqd", "пкд", "orgpage", "оргпейдж", "spravka inform", "справка информ",
    "2gis", "2гис", "yandex", "яндекс", "google", "гугл", "avito", "авито",
})


def is_aggregator_name(name: str) -> bool:
    """Проверяет, является ли имя названием самого агрегатора, а не компании.
    Например: "Uslugio", "Zoon", "PQD".
    """
    if not name:
        return False
    n = name.lower().strip()
    return n in _AGGREGATOR_NAMES


# ── A-5: Географическая валидация телефонов ────────────────────────────────
# DEF-коды для определения «местный» телефон или нет.
# Используются и в web_search.py (_is_local_phone), и в merger.py
# (merge_cluster — маркировка needs_review при не-локальных телефонах).

_MOSCOW_DEF_CODES = frozenset({"495", "499", "498"})
_SPB_DEF_CODES = frozenset({"812"})
_FEDERAL_DEF_CODES = frozenset({"800"})


def is_non_local_phone(phone: str, city: str) -> bool:
    """A-5: Проверяет, является ли телефон НЕ-локальным для данного города.

    Возвращает True если телефон явно из другого региона:
    - Московский DEF (495/499/498) для не-Москвы → True
    - Питерский DEF (812) для не-СПб → True
    - Федеральный (800) → False (всегда OK)
    - Мобильные и прочие → False (не подозрительно)

    Args:
        phone: Номер в формате E.164 (11 цифр, начинается с 7)
        city: Название города скрейпинга

    Returns:
        True если телефон подозрительно не-локальный, False если OK или неизвестно.
    """
    if not phone or len(phone) != 11 or not phone.startswith("7"):
        return False  # неизвестный формат — не помечаем
    def_code = phone[1:4]
    city_lower = city.lower() if city else ""

    # Федеральный номер — всегда OK
    if def_code in _FEDERAL_DEF_CODES:
        return False

    # Москва — московские коды ок
    if city_lower.startswith("москв") and def_code in _MOSCOW_DEF_CODES:
        return False

    # СПб — питерские коды ок
    if (city_lower.startswith("санкт-петербург") or city_lower.startswith("петербург")) and def_code in _SPB_DEF_CODES:
        return False

    # Московский DEF для не-Москвы → подозрительно
    if def_code in _MOSCOW_DEF_CODES:
        return True

    # Питерский DEF для не-СПб → подозрительно
    if def_code in _SPB_DEF_CODES:
        return True

    return False  # все остальные коды — норм


from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
import requests
from loguru import logger

# FIX 3.6: Подавляем SSL-предупреждения один раз при импорте модуля,
# а не при каждой SSL-ошибке в fetch_page/fetch_json.
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass


# ===== User-Agent =====
_USER_AGENTS = [
    # Chrome 135 (Windows + macOS)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    # Firefox 137
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:137.0) Gecko/20100101 Firefox/137.0",
    # Edge 135
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
    # Safari 17.4 (macOS)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


def get_random_ua() -> str:
    """Возвращает случайный User-Agent из списка."""
    return random.choice(_USER_AGENTS)


# Словарь транслитерации: сначала многосимвольные, потом односимвольные
# Порядок важен — щ, ш, ч, ж, ю, я обрабатываются до остальных
TRANSLIT_MAP = [
    ('щ', 'shch'), ('ш', 'sh'), ('ч', 'ch'), ('ж', 'zh'),
    ('ю', 'yu'), ('я', 'ya'), ('ё', 'yo'), ('э', 'e'),
    ('х', 'kh'), ('ц', 'ts'),
    ('а', 'a'), ('б', 'b'), ('в', 'v'), ('г', 'g'), ('д', 'd'),
    ('е', 'e'), ('з', 'z'), ('и', 'i'), ('й', 'y'), ('к', 'k'),
    ('л', 'l'), ('м', 'm'), ('н', 'n'), ('о', 'o'), ('п', 'p'),
    ('р', 'r'), ('с', 's'), ('т', 't'), ('у', 'u'), ('ф', 'f'),
    ('ъ', ''), ('ы', 'y'), ('ь', ''),
]


def slugify(text: str) -> str:
    """Транслитерация кириллицы в латиницу для URL (slug).
    Пример: "Волгоград" -> "volgograd", "Санкт-Петербург" -> "sankt-peterburg"
    """
    if not text:
        return ""
    
    text = text.lower().strip()
    for cyr, lat in TRANSLIT_MAP:
        text = text.replace(cyr, lat)
    
    # Очистка от спецсимволов, замена пробелов на дефис
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text).strip('-')
    
    return text


def adaptive_delay(min_sec: float = 1.0, max_sec: float = 3.5) -> float:
    """Случайная задержка между запросами. Имитирует поведение человека.

    Диапазон по умолчанию 1.0–3.5с вместо фиксированного sleep.
    Для Telegram использовать min=1.5 (из config: tg_finder.check_delay).
    """
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
    return delay


# FIX: TLD, которые НЕ являются email-доменами (файлы, изображения)
_FAKE_EMAIL_TLDS = frozenset({
    "jpg", "jpeg", "png", "gif", "svg", "webp", "bmp", "ico", "tif", "tiff",
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip", "rar", "7z",
    "mp4", "avi", "mov", "mp3", "wav", "css", "js", "html", "htm", "xml",
    "woff", "woff2", "ttf", "otf", "eot",
})

# FIX: Локальные части email, которые явно не являются адресами
_FAKE_EMAIL_LOCALS = frozenset({
    "photo", "image", "icon", "logo", "favicon", "banner", "bg", "background",
    "thumbnail", "thumb", "avatar", "placeholder", "sample", "demo", "test",
    "example", "email", "username", "user", "admin", "webmaster", "postmaster",
    "noreply", "no-reply", "mailer-daemon", "abuse", "root",
    "img", "src", "assets", "static", "media", "files", "upload", "uploads",
})

# FIX: DEF-коды, которые точно не могут быть мобильными/городскими РФ
_INVALID_DEF_CODES = frozenset({"000"})
# FIX: Подозрительные DEF-коды (бесплатный — не мастерская)
_SUSPICIOUS_DEF_CODES = frozenset({"800"})


def normalize_phone(phone: str) -> str | None:
    """Нормализация телефона к формату E.164: 7XXXXXXXXXX (без +).

    Обрабатывает: +79031234567, 89031234567, 9031234567,
                  +7 (903) 123-45-67, 8 (903) 123 45 67
    Возвращает: "79031234567" или None
    """
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None
    # Если начинается с 8 (российский формат) — заменяем на 7
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    # FIX: Если 10 цифр — НЕ добавляем 7 автоматически.
    # 10-значные числа могут быть ИНН, номерами счетов, id — не телефоны.
    # Принимаем только если начинаются с 9 (DEF-код мобильного РФ).
    elif len(digits) == 10:
        if digits.startswith("9"):
            digits = "7" + digits
        else:
            return None
    # Проверяем валидность: 11 цифр, начинается с 7
    if digits.startswith("7") and len(digits) == 11:
        # FIX: Проверяем DEF-код
        def_code = digits[1:4]
        if def_code in _INVALID_DEF_CODES:
            return None
        if def_code in _SUSPICIOUS_DEF_CODES:
            return None
        # FIX: Все цифры одинаковые / почти одинаковые
        if len(set(digits)) <= 2:
            return None
        return digits
    return None


def normalize_phones(phones: list[str]) -> list[str]:
    """Нормализация списка телефонов с дедупликацией."""
    result = []
    seen = set()
    for p in phones:
        norm = normalize_phone(p)
        if norm and norm not in seen:
            seen.add(norm)
            result.append(norm)
    return result


def extract_phones(text: str) -> list[str]:
    """Извлечение российских телефонных номеров из текста.

    Ищет номера формата: +7(903)123-45-67, 8 903 123 45 67,
    79031234567 и вариации с пробелами/дефисами/скобками.

    FIX: Post-validation через normalize_phone отсекает мусор (000, 800,
    одинаковые цифры).

    Returns:
        Список уникальных найденных телефонов (E.164).
    """
    if not text:
        return []
    raw = list(dict.fromkeys(re.findall(
        r"(\+?7[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2})",
        text,
    )))
    # FIX: Пропускаем через normalize_phone для отсева мусорных DEF-кодов
    result = []
    seen = set()
    for p in raw:
        norm = normalize_phone(p)
        if norm and norm not in seen:
            seen.add(norm)
            result.append(norm)
    return result


def extract_emails(text: str) -> list[str]:
    """Извлечение email из текста.

    FIX: Отсеиваем фейковые email:
    - TLD — расширение файла (.jpg, .png, .gif, etc.)
    - Локальная часть — явно не адрес (photo@, icon@, img@, etc.)
    - Паттерны изображений (photo@2x.domain.com)
    - Слишком короткие (< 3 символов локальная часть)
    - Двойные точки, ведущие/замыкающие точки
    """
    if not text:
        return []
    raw = list(dict.fromkeys(re.findall(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        text, re.IGNORECASE
    )))
    result = []
    for em in raw:
        em = em.strip().lower()
        if not em or "@" not in em:
            continue
        local, domain = em.rsplit("@", 1)
        if not local or not domain:
            continue
        # FIX: Локальная часть слишком короткая (но однобуквенные допустимы — a@b.com)
        if len(local) < 1:
            continue
        # FIX: TLD — расширение файла?
        tld = domain.rsplit(".", 1)[-1].lower()
        if tld in _FAKE_EMAIL_TLDS:
            continue
        # FIX 4.1: Локальная часть — явно не адрес?
        # Фильтруем независимо от TLD: photo@example.com тоже мусор.
        # Но пропускаем короткие locals (<=4 символов) — 'test', 'info', 'user'
        # часто являются легитимными email-адресами.
        local_base = local.split("+")[0]
        if local_base in _FAKE_EMAIL_LOCALS and len(local_base) >= 5:
            continue
        # FIX: Паттерны img@2x.example.com
        if re.match(r'^[a-z]+@\d+x?\.', em):
            continue
        # FIX: Паттерны типа name@2x.domain.com (из src атрибутов)
        if re.match(r'^.+@\d+x', em):
            continue
        # FIX: Двойные точки
        if ".." in em:
            continue
        # FIX: Точка в начале/конце локальной части
        if local.startswith(".") or local.endswith("."):
            continue
        # FIX: Нет точки в домене
        if "." not in domain:
            continue
        result.append(em)
    return result


def extract_domain(url: str) -> str | None:
    """Извлечение домена из URL."""
    if not url:
        return None
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain if domain else None
    except Exception as e:
        logger.debug(f"extract_domain failed for '{url}': {e}")
        return None


# B3: Домены мессенджеров и соцсетей — из единого constants.py
from granite.constants import MESSENGER_DOMAINS as _MESSENGER_DOMAINS
from granite.constants import NON_NETWORK_DOMAINS as _NON_NETWORK_DOMAINS


def extract_base_domain(website: str | None) -> str | None:
    """Извлечь базовый домен (SLD+TLD) из URL, игнорируя субдомены.

    Примеры:
        https://abaza.danila-master.ru/ → danila-master.ru
        https://www.gravestone.ru/      → gravestone.ru
        https://vk.com/                 → None (соцсеть, не сетевой маркер)

    Список исключений — NON_NETWORK_DOMAINS из granite/constants.py.
    """
    if not website:
        return None
    try:
        from urllib.parse import urlparse
        parsed = urlparse(website)
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return None
        parts = hostname.split(".")
        # Берём последние 2 части (SLD + TLD)
        # Для кириллических доменов (xn-- или .рф) тоже работает
        if len(parts) >= 2:
            base = ".".join(parts[-2:])
            if base in _NON_NETWORK_DOMAINS:
                return None
            return base
    except Exception:
        return None
    return None


def normalize_website_to_root(url: str) -> str | None:
    """Нормализация URL сайта к корню домена без path/query/fragment.

    Пример: https://diabaz-lux.ru/zakazat-pamyatnik → https://diabaz-lux.ru/
    Пример: diabaz-lux.ru → https://diabaz-lux.ru/

    B3: мессенджерные домены возвращают None — не являются сайтом компании.
    """
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not url:
        return None
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        netloc = parsed.netloc.lower()
        if not netloc or "." not in netloc:
            return None

        # B3: Исключить домены мессенджеров и соцсетей
        hostname = netloc.split(":")[0]
        if hostname in _MESSENGER_DOMAINS:
            return None

        scheme = parsed.scheme or "https"
        return f"{scheme}://{netloc}/"
    except Exception:
        return None


def compare_names(name_a: str, name_b: str, threshold: int = 88) -> bool:
    """Сравнение названий компаний. Возвращает True если схожи выше порога.

    Использует token_sort_ratio из rapidfuzz — устойчив к перестановке слов:
    "Гранит-Мастер Иванов" ≈ "Иванов Гранит-Мастер"
    """
    if not name_a or not name_b:
        return False
    a = name_a.lower().strip()
    b = name_b.lower().strip()
    # Точное совпадение (после нормализации)
    if a == b:
        return True
    # Fuzzy match
    score = fuzz.token_sort_ratio(a, b)
    return score >= threshold


def extract_street(address: str) -> str:
    """Базовое извлечение улицы из адреса.

    "г. Новосибирск, ул. Ленина, 45" → "ленина"
    "Новосибирск, проспект Маркса 12" → "маркса"
    """
    if not address:
        return ""
    address_lower = address.lower()
    # Убираем город
    for prefix in ["г. ", "город "]:
        if prefix in address_lower:
            address_lower = address_lower.split(prefix, 1)[-1]
            break
    # Извлекаем улицу
    match = re.search(r"(?:ул\.?|улица|пр-т\.?|проспект|пер\.?|переулок)\s*(.+?)[,\d]", address_lower)
    if match:
        return match.group(1).strip()
    return address_lower.split(",")[0].strip() if "," in address_lower else address_lower


# ===== URL Sanitization for Logs =====

def _sanitize_url_for_log(url: str, max_len: int = 80) -> str:
    """Sanitize URL before logging to avoid leaking PII.

    1. Strip query parameters (may contain phone numbers, session tokens)
    2. For wa.me/send?phone=... patterns, replace phone digits with ***
    3. Truncate to max_len characters
    """
    if not url or not isinstance(url, str):
        return "<no url>"
    # Handle wa.me phone pattern before stripping query params
    sanitized = re.sub(r'(wa\.me/send\?phone=)\d+', r'\1***', url)
    # Strip query parameters
    sanitized = sanitized.split('?')[0]
    # Strip fragment
    sanitized = sanitized.split('#')[0]
    # Truncate
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len] + "..."
    return sanitized


# ===== HTTP-запросы с retry =====

class NetworkError(Exception):
    """Сайт не отвечает после всех попыток."""
    pass


class SiteNotFoundError(Exception):
    """Сайт возвращает 404 — не нужно повторять."""
    pass


# Retry для временных ошибок (502, 503, timeout, connection)
# НЕ retry для 404, 403 и 429 (заблокировали / rate limit)
def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, SiteNotFoundError):
        return False
    if isinstance(exc, requests.exceptions.HTTPError):
        response = exc.response
        if response is not None and response.status_code in (403, 404, 429):
            return False
    return True


# ИСПРАВЛЕНО: retry_if_exception (callable) вместо retry_if_exception_type (тип)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception(_should_retry),
    reraise=True,
)
def fetch_page(url: str, timeout: int = 15) -> str:
    """Получение HTML страницы с retry и логированием.

    Raises:
        NetworkError: после 3 неудачных попыток
        SiteNotFoundError: при 404
        ValueError: если URL не прошёл проверку безопасности (SSRF)
    """
    if not is_safe_url(url):
        raise ValueError(f"URL blocked by safety check: {url[:60]}")
    headers = {"User-Agent": get_random_ua()}
    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if response.status_code == 404:
            logger.warning(f"404 — {_sanitize_url_for_log(url)}")
            raise SiteNotFoundError(f"404: {url}")
        response.raise_for_status()
        return response.text
    except requests.exceptions.SSLError as e:
        # SSL verification failed (self-signed cert, hostname mismatch) —
        # retry with verify=False as fallback
        logger.debug(f"SSL error for {_sanitize_url_for_log(url)}, retrying with verify=False")
        try:
            response = requests.get(url, headers=headers, timeout=timeout,
                                   allow_redirects=True, verify=False)
            if response.status_code == 404:
                raise SiteNotFoundError(f"404: {url}")
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e2:
            logger.warning(f"SSL fallback also failed: {_sanitize_url_for_log(url)} — {e2}")
            raise NetworkError(f"SSL failed: {url}") from e2
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"Connection error: {_sanitize_url_for_log(url)} — {e}")
        raise NetworkError(f"Connection failed: {url}") from e
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout: {_sanitize_url_for_log(url)}")
        raise NetworkError(f"Timeout: {url}")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        logger.warning(f"HTTP {status}: {_sanitize_url_for_log(url)}")
        raise


def check_site_alive(url: str) -> int | None:
    """HEAD-запрос для проверки, живой ли сайт. Возвращает статус-код или None.

    Использует allow_redirects=True для корректной обработки HTTP→HTTPS
    редиректов (301/302). Без follow redirects сайты с HTTP→HTTPS считались
    бы «мёртвыми», и обогащение (мессенджеры, CMS) бы пропускалось.
    """
    if not url:
        return None
    if not is_safe_url(url):
        raise ValueError(f"URL blocked by safety check: {url[:60]}")
    try:
        headers = {"User-Agent": get_random_ua()}
        r = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
        return r.status_code
    except requests.exceptions.SSLError:
        # SSL verification failed — retry with verify=False
        try:
            headers = {"User-Agent": get_random_ua()}
            r = requests.head(url, headers=headers, timeout=10, allow_redirects=True, verify=False)
            return r.status_code
        except Exception:
            return None
    except Exception as e:
        logger.debug(f"check_site_alive failed for '{_sanitize_url_for_log(url, 60)}': {e}")
        return None


def sanitize_filename(name: str) -> str:
    """Санитизация имени файла: транслитерация кириллицы + очистка.

    Используется в экспортерах и дедуп-модулях для безопасного создания файлов
    из пользовательских данных (названия городов, компаний).
    Кириллица транслитерируется через TRANSLIT_MAP вместо замены на '_'.
    """
    if not name:
        return "unnamed"
    # Транслитерация кириллицы (без полной очистки slugify, которая убивает спецсимволы)
    name_lower = name.lower().strip()
    for cyr, lat in TRANSLIT_MAP:
        name_lower = name_lower.replace(cyr, lat)
    # Очистка от небезопасных символов
    name_slug = re.sub(r'[^a-z0-9_-]', '_', name_lower)
    name_slug = re.sub(r'_+', '_', name_slug)
    name_slug = name_slug.strip('_-')
    return name_slug[:100] if name_slug else "unnamed"


def pick_best_value(*values: str) -> str:
    """Из нескольких значений берёт самое длинное (полное)."""
    candidates = [v.strip() for v in values if v and v.strip()]
    if not candidates:
        return ""
    return max(candidates, key=len)


# ===== URL Safety =====

def is_safe_url(url: str) -> bool:
    """Check that URL is not pointing to internal/private resources.

    Blocks: localhost, private IPs (RFC 1918), link-local, loopback,
    cloud-metadata (169.254), CGNAT (100.64/10), IPv6 ULA (fd00::/7),
    and other internal ranges.  Uses ipaddress module for reliable
    IPv4/IPv6 parsing (handles IPv6-mapped IPv4, brackets, etc.).
    """
    if not url or not isinstance(url, str):
        return False
    cleaned = re.sub(r'[\s\x00]+', '', url).split()[0]
    if not cleaned:
        return False
    try:
        parsed = urlparse(cleaned)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    hostname_lower = hostname.lower()
    # Block known internal hostnames
    if hostname_lower in ("localhost", "metadata.google.internal", "metadata"):
        return False
    # Try ipaddress-based check (handles IPv4, IPv6, brackets, mapped addrs)
    try:
        import ipaddress
        ip = ipaddress.ip_address(hostname_lower)
        # Handle IPv6-mapped IPv4 (e.g. ::ffff:127.0.0.1)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        private_ranges = [
            ipaddress.ip_network("127.0.0.0/8"),      # loopback
            ipaddress.ip_network("10.0.0.0/8"),        # RFC 1918
            ipaddress.ip_network("172.16.0.0/12"),     # RFC 1918
            ipaddress.ip_network("192.168.0.0/16"),    # RFC 1918
            ipaddress.ip_network("169.254.0.0/16"),    # link-local / cloud metadata
            ipaddress.ip_network("0.0.0.0/8"),         # "this" network
            ipaddress.ip_network("100.64.0.0/10"),     # CGNAT / shared address space
            ipaddress.ip_network("192.0.0.0/24"),      # IETF protocol assignments
            ipaddress.ip_network("192.0.2.0/24"),      # TEST-NET-1 (documentation)
            ipaddress.ip_network("198.51.100.0/24"),   # TEST-NET-2
            ipaddress.ip_network("203.0.113.0/24"),    # TEST-NET-3
            ipaddress.ip_network("::1/128"),            # loopback
            ipaddress.ip_network("::/128"),            # unspecified
            ipaddress.ip_network("fc00::/7"),          # IPv6 ULA
            ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
        ]
        for net in private_ranges:
            if ip in net:
                return False
    except ValueError:
        pass  # hostname is not an IP — continue with string checks below

    # Fast string-based checks for hostnames that resolve to internal IPs
    # (defense-in-depth; ipaddress above handles pure-IP hostnames)
    if hostname_lower.startswith(("127.", "10.", "192.168.", "169.254.", "0.")):
        return False
    if hostname_lower.startswith("172."):
        parts = hostname_lower.split(".")
        if len(parts) >= 2:
            try:
                second = int(parts[1])
                if 16 <= second <= 31:
                    return False
            except ValueError:
                pass
    if hostname_lower.startswith("100."):
        parts = hostname_lower.split(".")
        if len(parts) >= 2:
            try:
                second = int(parts[1])
                if 64 <= second <= 127:
                    return False
            except ValueError:
                pass
    return True


def is_safe_link_url(url: str) -> bool:
    """Check URL is safe for embedding in markdown links / hrefs.
    Rejects javascript:, data:, vbscript: and other dangerous schemes.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


# ===== Error classification =====

# Категории ошибок для классификации
ERROR_NETWORK = "network"
ERROR_PARSING = "parsing"
ERROR_DATA = "data"


def classify_error(exc: Exception) -> str:
    """Классифицировать ошибку по типу.

    Returns:
        Строковую категорию: 'network', 'parsing', 'data'.
    """
    exc_name = type(exc).__name__.lower()
    exc_msg = str(exc).lower()
    if any(k in exc_name or k in exc_msg for k in (
        "timeout", "connection", "network", "ssl", "dns",
    )):
        return ERROR_NETWORK
    if any(k in exc_name or k in exc_msg for k in (
        "403", "captcha", "blocked", "parse", "json",
    )):
        return ERROR_PARSING
    return ERROR_DATA


# ===== HTML → Plain Text =====

def html_to_plain_text(html_body: str) -> str:
    """Конвертировать HTML в plain text для MIMEText("plain") альтернативы.

    Использует BeautifulSoup (уже в зависимостях) для корректного извлечения текста:
    - Вырезает <script> и <style>
    - Заменяет блочные теги на переводы строк
    - Декодирует HTML-сущности (&amp; → &, &nbsp; → пробел)

    Не используется regex re.sub(r'<[^>]+>', '', html) — наивный подход
    ломается на сущностях, скриптах, стилях и переводах строк.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_body, "html.parser")
    # Удалить скрипты и стили
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # Убрать избыточные пустые строки
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned


def classify_messenger(url: str, messengers: dict) -> None:
    """Классифицировать URL мессенджера и добавить в dict.

    Shared helper для jsprav.py и jsprav_playwright.py (LOW-7: DRY).
    Определяет тип мессенджера по URL и записывает в messengers dict.
    YouTube пропускается — не является мессенджером для CRM.
    """
    url_lower = url.lower()
    if "t.me" in url_lower:
        messengers["telegram"] = url
    elif "vk.com" in url_lower or "vkontakte" in url_lower:
        messengers["vk"] = url
    elif "viber" in url_lower:
        messengers["viber"] = url
    elif "wa.me" in url_lower or "whatsapp" in url_lower:
        messengers["whatsapp"] = url
    elif "ok.ru" in url_lower:
        messengers["odnoklassniki"] = url
    elif "youtube" in url_lower or "youtu.be" in url_lower:
        pass  # YouTube — не мессенджер, пропускаем
    elif "instagram" in url_lower:
        messengers["instagram"] = url
