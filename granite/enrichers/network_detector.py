# enrichers/network_detector.py
from granite.database import Database, EnrichedCompanyRow
from loguru import logger
from granite.utils import extract_domain, normalize_phone as _normalize_phone


class NetworkDetector:
    """Выявляет сети (филиалы одного бизнеса).

    Сеть определяется по двум признакам:
    1. Один и тот же домен сайта у 2+ компаний → сеть.
    2. Один и тот же нормализованный телефон у 2+ компаний → сеть.

    Оптимизация: вместо загрузки всех ORM-объектов в память используются
    лёгкие tuple-запросы (id, website, phones) и массовый UPDATE через IN.
    """

    def __init__(self, db: Database):
        self.db = db

    def scan_for_networks(self, threshold: int = 2, city: str | None = None) -> None:
        """Пересчитывает флаг is_network. Если передан city — только для этой области."""
        with self.db.session_scope() as session:
            # Сбрасываем флаги для целевой области (или всех)
            base_q = session.query(EnrichedCompanyRow)
            if city:
                base_q = base_q.filter_by(city=city)
            reset_count = base_q.update(
                {EnrichedCompanyRow.is_network: False}, synchronize_session=False
            )
            session.flush()

            # Загружаем только (id, website, phones) — лёгкие tuple без ORM-объектов
            rows_q = session.query(
                EnrichedCompanyRow.id,
                EnrichedCompanyRow.website,
                EnrichedCompanyRow.phones,
            )
            if city:
                rows_q = rows_q.filter_by(city=city)

            rows = rows_q.all()
            if not rows:
                logger.info("Нет компаний для анализа сетей.")
                return

            # ── Признак 1: домены ──
            domain_count: dict[str, int] = {}
            for _id, website, _phones in rows:
                domain = extract_domain(website)
                if domain:
                    domain_count[domain] = domain_count.get(domain, 0) + 1

            network_domains = {d for d, cnt in domain_count.items() if cnt >= threshold}

            # ── Признак 2: телефоны (нормализованные) ──
            phone_count: dict[str, int] = {}
            for _id, _website, phones in rows:
                for p in phones or []:
                    norm = _normalize_phone(p)
                    if norm:
                        phone_count[norm] = phone_count.get(norm, 0) + 1

            network_phones = {p for p, cnt in phone_count.items() if cnt >= threshold}

            # Логируем что нашли
            if network_domains:
                for d in sorted(network_domains):
                    logger.debug(f"  Сеть по домену: {d} ({domain_count[d]} компаний)")
            if network_phones:
                for p in sorted(network_phones):
                    logger.debug(f"  Сеть по телефону: {p} ({phone_count[p]} компаний)")

            if not network_domains and not network_phones:
                logger.info("Сетей не обнаружено.")
                return

            # ── Применяем флаги — один UPDATE через WHERE id IN (...) ──
            network_ids: list[int] = []
            for row_id, website, phones in rows:
                domain = extract_domain(website)
                is_net = domain in network_domains

                if not is_net:
                    for p in phones or []:
                        if _normalize_phone(p) in network_phones:
                            is_net = True
                            break

                if is_net:
                    network_ids.append(row_id)

            if network_ids:
                # Массовый UPDATE чанками по 500 (SQLite LIMIT в execute)
                chunk_size = 500
                for i in range(0, len(network_ids), chunk_size):
                    chunk = network_ids[i : i + chunk_size]
                    update_q = session.query(EnrichedCompanyRow).filter(
                        EnrichedCompanyRow.id.in_(chunk)
                    )
                    update_q.update(
                        {EnrichedCompanyRow.is_network: True}, synchronize_session=False
                    )

            logger.info(
                f"Обнаружено {len(network_ids)} филиалов сетей "
                f"(доменов: {len(network_domains)}, телефонов: {len(network_phones)})."
            )
