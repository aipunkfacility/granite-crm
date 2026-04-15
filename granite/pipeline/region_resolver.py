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

__all__ = ["STANDARD_SOURCES", "RegionResolver"]

STANDARD_SOURCES = ["jsprav", "web_search", "dgis", "yell"]

_DEFAULT_REGIONS_PATH = Path(__file__).parent.parent.parent / "data" / "regions.yaml"


# Thread-safe: written once at first call, then only reads
_regions_lock = threading.Lock()
_REGIONS_CACHE: dict | None = None


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
