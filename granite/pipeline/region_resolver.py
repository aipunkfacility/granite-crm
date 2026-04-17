# pipeline/region_resolver.py
"""Разрешение регионов и проверка конфигурации источников.

Источник истины — data/regions.yaml (1098 городов, 82 региона).
config.yaml больше не содержит список городов.
5 городов с дублирующимися названиями в разных регионах
(Гурьевск, Железногорск, Кировск, Михайловск, Троицк)
— get_all_cities() вернёт 1093 уникальных.

Режимы работы:
  - `run Город`        → скрапинг одного города (если есть в regions.yaml)
  - `run Область`      → скрапинг всех городов области
  - `run all`          → скрапинг всех городов из regions.yaml
"""

import yaml
import threading
from pathlib import Path
from loguru import logger

__all__ = [
    "STANDARD_SOURCES", "RegionResolver",
    "build_city_lookup", "detect_city", "lookup_region",
    "seed_cities_table", "_load_regions",
]

STANDARD_SOURCES = ["jsprav", "web_search", "dgis", "yell"]

_DEFAULT_REGIONS_PATH = Path(__file__).parent.parent.parent / "data" / "regions.yaml"


# Thread-safe: written once at first call, then only reads
_regions_lock = threading.Lock()
_REGIONS_CACHE: dict | None = None
_CITY_TO_REGION_CACHE: dict[str, str] | None = None


def _load_regions(path: str | None = None) -> dict:
    """Загрузка data/regions.yaml в кэш (один раз за запуск).

    Возвращает {region_name: [city1, city2, ...], ...}.
    """
    global _REGIONS_CACHE
    if _REGIONS_CACHE is not None:
        return _REGIONS_CACHE

    with _regions_lock:
        if _REGIONS_CACHE is not None:
            return _REGIONS_CACHE

        filepath = Path(path) if path else _DEFAULT_REGIONS_PATH
        if not filepath.exists():
            logger.warning(f"Файл {filepath} не найден, справочник городов недоступен")
            _REGIONS_CACHE = {}
            return _REGIONS_CACHE

        with open(filepath, "r", encoding="utf-8") as f:
            _REGIONS_CACHE = yaml.safe_load(f) or {}

        if not isinstance(_REGIONS_CACHE, dict):
            logger.warning("Invalid regions.yaml format: expected dict")
            _REGIONS_CACHE = {}

    total = sum(len(cities) for cities in _REGIONS_CACHE.values())
    logger.info(f"Загружен справочник: {len(_REGIONS_CACHE)} регионов, {total} городов")
    return _REGIONS_CACHE


# ── Стоп-слова — не могут быть корнями городов ──────────────────────────
_STOP_WORDS = frozenset({
    "область", "край", "республика", "автономный", "округ",
    "район", "поселок", "посёлок", "деревня", "село", "станица",
    "город", "г.", "пгт", "р-н",
})


# ── Модульный кэш для build_city_lookup ─────────────────────────────────
_CITY_LOOKUP_CACHE: tuple[dict[str, str | None], list[str]] | None = None


def build_city_lookup() -> tuple[dict[str, str | None], list[str]]:
    """Построить lookup-структуру для поиска городов в тексте.

    Returns:
        (city_lookup, sorted_roots)
        - city_lookup: {variant_lower: canonical_name | None}
          {"абакан": "Абакан", "абаканск": "Абакан", ...}
          None = двойник (неоднозначно, skip в detect_city)
        - sorted_roots: список корней, отсортированных по длине DESC
          (длинные первыми для приоритета)

    Корни для каждого города (len >= 5, не в _STOP_WORDS):
        - Полное имя lowercase: "москва"
        - Префикс len-1 (для падежей): "москв" ловит "Москве"
        - Корень без "ь": "пермь" → "перм" ловит "в Перми"

    Кэшируется на уровне модуля — вызывается один раз.
    """
    global _CITY_LOOKUP_CACHE
    if _CITY_LOOKUP_CACHE is not None:
        return _CITY_LOOKUP_CACHE

    regions = _load_regions()

    # Считаем двойников: города, чьё имя встречается > 1 раза
    name_counts: dict[str, int] = {}
    for cities in regions.values():
        if isinstance(cities, list):
            for city in cities:
                name_counts[city] = name_counts.get(city, 0) + 1

    city_lookup: dict[str, str | None] = {}
    roots_set: set[str] = set()

    for region_name, cities in regions.items():
        if not isinstance(cities, list):
            continue
        for city in cities:
            is_doppel = name_counts.get(city, 0) > 1
            name_lower = city.lower()

            # Полное имя lowercase
            city_lookup[name_lower] = None if is_doppel else city
            if len(name_lower) >= 5 and name_lower not in _STOP_WORDS:
                roots_set.add(name_lower)

            # Префикс для падежей: "Москв" ловит "Москве"
            if len(name_lower) >= 5:
                prefix_len = max(5, len(name_lower) - 1)
                prefix = name_lower[:prefix_len]
                if prefix != name_lower and prefix not in _STOP_WORDS:
                    city_lookup[prefix] = None if is_doppel else city
                    roots_set.add(prefix)

            # Города на "ь": "Пермь" → "перм" ловит "в Перми"
            if name_lower.endswith("ь") and len(name_lower) >= 5:
                root_no_soft = name_lower[:-1]
                if root_no_soft not in _STOP_WORDS:
                    city_lookup[root_no_soft] = None if is_doppel else city
                    roots_set.add(root_no_soft)

    # Сортируем по длине DESC (длинные совпадения имеют приоритет)
    sorted_roots = sorted(roots_set, key=len, reverse=True)
    _CITY_LOOKUP_CACHE = (city_lookup, sorted_roots)
    return _CITY_LOOKUP_CACHE


def _match_score(text: str, pos: int) -> int:
    """Вычислить score совпадения по контексту вокруг позиции.

    Returns:
        3 — после предлога ("в Абакане", "из Москвы")
        2 — после разделителя (", ", " — ", " - ")
        1 — в начале строки или после пробела (без контекста)
        0 — не совпадает (внутри другого слова)
    """
    if pos > 0 and text[pos - 1].isalpha():
        return 0  # внутри другого слова

    if pos == 0:
        return 1

    prefix = text[:pos]
    # Предлоги (сохраняем trailing space для проверки)
    for prep in ("в ", "из ", "для ", "по ", "от ", "до ", "при ", "г. "):
        if prefix.endswith(prep):
            return 3
    # Разделители (strip trailing whitespace)
    stripped = prefix.rstrip()
    if stripped and stripped[-1] in (",", "—", "-", ".", ":"):
        return 2
    return 1


def detect_city(
    text: str,
    exclude_city: str | None = None,
) -> str | None:
    """Найти упоминание города из regions.yaml в тексте.

    Score-based: ищет все совпадения, возвращает с максимальным score.
    При равном score — более длинное совпадение (longest match).

    Args:
        text: enriched name + address для анализа
        exclude_city: текущий город (не переназначать в себя)

    Returns:
        Canonical city name или None.

    Примеры:
        "Гранитная мастерская в Абакане" → "Абакан" (score=3, prep "в ")
        "ул. Промышленная, 7Е, Абакан" → "Абакан" (score=2, after ",")
        "Памятники Абаза" exclude="Абаза" → None
        "Памятники Кировск" → None  # двойник, неоднозначно
        "Гранит Хакасии" → None     # "хакасии" в _STOP_WORDS (нет, но корень короткий)
    """
    if not text:
        return None

    text_lower = text.lower()
    city_lookup, sorted_roots = build_city_lookup()

    best_match: str | None = None
    best_score = 0
    best_len = 0

    for root in sorted_roots:
        canonical = city_lookup.get(root)
        if canonical is None:
            continue  # двойник — skip
        if canonical == exclude_city:
            continue  # текущий город — skip

        pos = 0
        while True:
            pos = text_lower.find(root, pos)
            if pos == -1:
                break

            score = _match_score(text_lower, pos)
            if score > 0:
                if score > best_score or (score == best_score and len(root) > best_len):
                    best_match = canonical
                    best_score = score
                    best_len = len(root)
            pos += 1

    return best_match


def lookup_region(city: str) -> str:
    """Найти регион для города по regions.yaml (без экземпляра RegionResolver).

    Returns:
        Название региона или "" если не найден.
        ("" вместо None — NOT NULL в БД)
    """
    regions = _load_regions()
    # Обратный индекс: {city: region}, кэшируется на уровне модуля
    global _CITY_TO_REGION_CACHE
    if _CITY_TO_REGION_CACHE is None:
        _CITY_TO_REGION_CACHE = {}
        for region_name, cities in regions.items():
            if isinstance(cities, list):
                for c in cities:
                    if c not in _CITY_TO_REGION_CACHE:  # первое вхождение
                        _CITY_TO_REGION_CACHE[c] = region_name
    return _CITY_TO_REGION_CACHE.get(city, "")


def seed_cities_table(db) -> int:
    """Заполнить cities_ref из regions.yaml.

    Безопасен для повторного вызова:
    - Проверяет что таблица уже заполнена (count > 0 → skip)
    - Использует INSERT OR IGNORE для защиты от дублей

    Args:
        db: экземпляр Database (granite.database.Database).

    Returns:
        Количество вставленных строк.
    """
    from granite.database import CityRefRow

    regions = _load_regions()
    if not regions:
        logger.warning("regions.yaml пуст — нечего seed-ить")
        return 0

    # Считаем двойников
    name_counts: dict[str, int] = {}
    for cities in regions.values():
        if isinstance(cities, list):
            for city in cities:
                name_counts[city] = name_counts.get(city, 0) + 1

    with db.session_scope() as session:
        # Не вставлять если уже заполнено
        if session.query(CityRefRow).count() > 0:
            logger.debug("cities_ref уже заполнена — skip")
            return 0

        count = 0
        seen_cities: set[str] = set()
        for region_name, cities in regions.items():
            if not isinstance(cities, list):
                continue
            for city in cities:
                # Для городов-двойников (Кировск и др.) сохраняется первое вхождение.
                # is_doppelganger=True обеспечивает что detect_city() не вернёт их.
                if city in seen_cities:
                    continue
                seen_cities.add(city)
                session.add(CityRefRow(
                    name=city,
                    region=region_name,
                    is_doppelganger=(name_counts.get(city, 0) > 1),
                ))
                count += 1

        session.flush()
        logger.info(f"cities_ref: заполнено {count} городов")
        return count


class RegionResolver:
    """Работа с конфигурацией городов и областей.

    Источник истины — data/regions.yaml.
    """

    def __init__(self, config: dict, regions_path: str | None = None):
        self.config = config
        self._regions = _load_regions(regions_path)

    def _find_city_region(self, city: str) -> str | None:
        """Найти регион для города по названию."""
        for region, cities in self._regions.items():
            if isinstance(cities, list) and city in cities:
                return region
        return None

    def get_region_cities(self, city_or_region: str) -> list[str]:
        """Вернуть список городов для скрапинга.

        Логика:
        1. Если name == 'all' → все города из regions.yaml.
        2. Если name — название города (есть в regions.yaml) → [город].
        3. Если name — название региона (ключ в regions.yaml) → все города региона.
        4. Иначе → [name] как есть (для совместимости).

        Порядок 2→3 важен: если город и регион называются одинаково (Москва),
        приоритет у города.
        """
        # 1. Все города
        if city_or_region.lower() == "all":
            all_cities = []
            for cities in self._regions.values():
                if isinstance(cities, list):
                    all_cities.extend(cities)
            return sorted(set(all_cities))

        # 2. Название города — проверяем есть ли в regions.yaml
        region = self._find_city_region(city_or_region)
        if region:
            return [city_or_region]

        # 3. Название региона
        if city_or_region in self._regions:
            cities = self._regions[city_or_region]
            if isinstance(cities, list):
                return cities
            return [city_or_region]

        # 4. Fallback — возвращаем как есть
        logger.warning(
            f"'{city_or_region}' не найден в regions.yaml — будет использован как есть"
        )
        return [city_or_region]

    def get_region_for_city(self, city: str) -> str:
        """Вернуть название региона для города.

        Если город не найден — возвращает название города (как регион).
        """
        region = self._find_city_region(city)
        return region if region else city

    def get_all_cities(self) -> list[str]:
        """Вернуть все города из regions.yaml."""
        all_cities = []
        for cities in self._regions.values():
            if isinstance(cities, list):
                all_cities.extend(cities)
        return sorted(set(all_cities))

    def get_all_regions(self) -> list[str]:
        """Вернуть все названия регионов."""
        return list(self._regions.keys())

    def is_source_enabled(self, source: str) -> bool:
        """Проверить включён ли источник в config.yaml."""
        return self.config.get("sources", {}).get(source, {}).get("enabled", True)

    def get_active_sources(self, sources: list[str] | None = None) -> list[str]:
        """Вернуть список включённых источников.

        Args:
            sources: список источников для проверки (по умолчанию все стандартные).
        """
        if sources is None:
            sources = STANDARD_SOURCES
        return [s for s in sources if self.is_source_enabled(s)]
