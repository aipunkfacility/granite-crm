# dedup/phone_cluster.py
from collections import defaultdict
from granite.utils import normalize_phone


def cluster_by_phones(
    raw_companies: list[dict],
    network_phone_threshold: int = 10,
) -> list[list[int]]:
    """Группировка записей по общим номерам телефонов (Union-Find).

    Args:
        raw_companies: список dict с полями {"id": int, "phones": list[str]}
        network_phone_threshold: телефоны, встречающиеся у >= N компаний,
            считаются сетевыми и исключаются из кластеризации.
            Это предотвращает ложное слияние 141 компании Данила-Мастер
            в один кластер по федеральному номеру.

    Returns:
        Список кластеров: [[id1, id2, id3], [id4, id5], ...]
        Записи с общим номером → один кластер (транзитивно).
    """
    # Шаг 1: подсчёт частоты каждого телефона
    phone_to_ids: dict[str, set[int]] = defaultdict(set)
    for company in raw_companies:
        cid = company.get("id")
        if cid is None:
            continue
        for phone in company.get("phones", []):
            norm = normalize_phone(phone)
            if norm:
                phone_to_ids[norm].add(cid)

    # Шаг 2: исключить сетевые телефоны
    network_phones = {
        phone for phone, ids in phone_to_ids.items()
        if len(ids) >= network_phone_threshold
    }
    if network_phones:
        from loguru import logger
        logger.info(
            f"phone_cluster: исключено {len(network_phones)} сетевых телефонов "
            f"(threshold={network_phone_threshold}): "
            f"{', '.join(list(network_phones)[:3])}{'...' if len(network_phones) > 3 else ''}"
        )

    # Шаг 3: Union-Find только по не-сетевым телефонам
    id_to_cluster: dict[int, set[int]] = {}

    for phone, ids in phone_to_ids.items():
        if phone in network_phones:
            continue  # пропускаем сетевые телефоны
        if len(ids) < 2:
            continue  # Один владелец номера — не кластер

        # Найти существующие кластеры, которые пересекаются с текущими ids
        connected: set[int] = set()
        for cid in ids:
            if cid in id_to_cluster:
                connected.update(id_to_cluster[cid])

        # Новый кластер = объединение всех найденных + текущие ids
        new_cluster = connected | ids
        for cid in new_cluster:
            id_to_cluster[cid] = new_cluster

    # Убираем дубли кластеров
    seen: set[frozenset] = set()
    clusters = []
    for cid, cluster in id_to_cluster.items():
        cluster_key = frozenset(cluster)
        if cluster_key not in seen:
            seen.add(cluster_key)
            clusters.append(list(cluster))

    return clusters
