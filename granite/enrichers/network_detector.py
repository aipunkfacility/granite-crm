# enrichers/network_detector.py
import re
from granite.database import Database, EnrichedCompanyRow
from loguru import logger
from granite.utils import extract_domain, normalize_phone as _normalize_phone


class NetworkDetector:
    """Выявляет сети (филиалы одного бизнеса).

    Сеть определяется по двум признакам:
    1. Один и тот же домен сайта у 2+ компаний → сеть.
    2. Один и тот же нормализованный телефон у 2+ компаний → сеть.
    """

    def __init__(self, db: Database):
        self.db = db

    def scan_for_networks(self, threshold: int = 2, city: str = None) -> None:
        """Пересчитывает флаг is_network. Если передан city — только для этой области."""
        session = self.db.get_session()
        try:
            # Сбрасываем флаги для целевой области (или всех)
            query = session.query(EnrichedCompanyRow)
            if city:
                query = query.filter_by(city=city)
            query.update({EnrichedCompanyRow.is_network: False})

            # Берём компании для сканирования
            all_companies = query.all()
            if not all_companies:
                logger.info("Нет компаний для анализа сетей.")
                return

            # ── Признак 1: домены ──
            domain_count: dict[str, int] = {}
            for c in all_companies:
                domain = extract_domain(c.website)
                if domain:
                    domain_count[domain] = domain_count.get(domain, 0) + 1

            network_domains = {d for d, cnt in domain_count.items() if cnt >= threshold}

            # ── Признак 2: телефоны (нормализованные) ──
            phone_count: dict[str, int] = {}
            for c in all_companies:
                for p in (c.phones or []):
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

            # ── Применяем флаги ──
            update_count = 0
            for c in all_companies:
                domain = extract_domain(c.website)
                is_net = domain in network_domains

                if not is_net:
                    for p in (c.phones or []):
                        if _normalize_phone(p) in network_phones:
                            is_net = True
                            break

                if is_net:
                    c.is_network = True
                    update_count += 1

            session.commit()
            logger.info(
                f"Обнаружено {update_count} филиалов сетей "
                f"(доменов: {len(network_domains)}, телефонов: {len(network_phones)})."
            )

        except Exception as e:
            logger.error(f"NetworkDetector error: {e}")
            session.rollback()
        finally:
            session.close()
