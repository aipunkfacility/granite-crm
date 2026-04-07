# dedup/name_matcher.py
from granite.utils import compare_names
from collections import defaultdict
from loguru import logger


def find_name_matches(companies: list[dict], threshold: int = 88) -> list[list[int]]:
    """Поиск дубликатов по названиям через fuzzy matching.

    Оптимизация: блокировка по первой букве названия — сравниваем только
    компании у которых совпадает первая буква. Сильно сокращает число
    сравнений на больших выборках.

    Args:
        companies: список dict с полями {"id": int, "name": str, "address": str}
        threshold: порог схожести (0-100, из config.yaml dedup.name_similarity_threshold)

    Returns:
        Список пар/групп: [[id1, id2], ...] — похожие названия
    """
    matches = []

    # Блокировка по первой букве названия
    blocks: dict[str, list[dict]] = defaultdict(list)
    for company in companies:
        name_lower = company.get("name", "").lower().strip()
        if not name_lower:
            continue
        key = name_lower[0] if name_lower[0].isalpha() else "#"
        blocks[key].append(company)

    total_comparisons = 0
    for key, block_companies in blocks.items():
        n = len(block_companies)
        # Пропускаем блоки из 1 записи
        if n < 2:
            continue
        for i in range(n):
            for j in range(i + 1, n):
                total_comparisons += 1
                if compare_names(block_companies[i]["name"], block_companies[j]["name"], threshold):
                    matches.append([block_companies[i]["id"], block_companies[j]["id"]])

    logger.debug(f"Name matcher: {len(companies)} компаний, {total_comparisons} сравнений, {len(matches)} совпадений")
    return matches
