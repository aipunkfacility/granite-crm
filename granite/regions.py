# regions.py — список городов по областям из статичного файла
import yaml
from loguru import logger
from pathlib import Path


# Thread-safe: written once at first call, then only reads
_REGIONS_CACHE: dict | None = None


def _load_regions(path: str = "data/regions.yaml") -> dict:
    """Загрузка data/regions.yaml в кэш (один раз за запуск)."""
    global _REGIONS_CACHE
    if _REGIONS_CACHE is not None:
        return _REGIONS_CACHE

    filepath = Path(path)
    if not filepath.exists():
        logger.warning(f"Файл {path} не найден, города по области не будут добавлены")
        _REGIONS_CACHE = {}
        return _REGIONS_CACHE

    with open(filepath, "r", encoding="utf-8") as f:
        _REGIONS_CACHE = yaml.safe_load(f) or {}

    total = sum(len(cities) for cities in _REGIONS_CACHE.values())
    logger.info(f"Загружен справочник: {len(_REGIONS_CACHE)} областей, {total} городов")
    return _REGIONS_CACHE


def get_region_cities(region: str) -> list[str]:
    """Вернуть список городов для области.

    Если область не найдена в regions.yaml — пустой список.
    """
    regions = _load_regions()
    cities = regions.get(region, [])
    return cities or []
