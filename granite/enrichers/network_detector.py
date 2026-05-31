# enrichers/network_detector.py
from granite.database import Database, EnrichedCompanyRow
from loguru import logger
from granite.utils import extract_domain, extract_base_domain, normalize_phone
from granite.constants import FREE_EMAIL_DOMAINS


class NetworkDetector:
    """Выявляет сети (филиалы одного бизнеса).

    Сеть определяется по четырём признакам:
    1. Один и тот же домен сайта у 2+ компаний → сеть.
    2. Один и тот же базовый домен (SLD+TLD) у 2+ компаний → сеть
       (ловит субдоменные сети типа *.danila-master.ru).
    3. Один и тот же нормализованный телефон у 2+ компаний → сеть.
    4. Один и тот же email-домен у 2+ компаний → сеть.

    Оптимизация: вместо загрузки всех ORM-объектов в память используются
    лёгкие tuple-запросы (id, website, phones, emails) и массовый UPDATE через IN.
    """

    def __init__(self, db: Database, config: dict | None = None):
        self.db = db
        self.config = config or {}

    def _get_threshold(self) -> int:
        """Порог из конфига или дефолт."""
        return self.config.get("enrichment", {}).get("network_threshold", 2)

    def scan_for_networks(self, threshold: int | None = None, city: str | None = None) -> None:
        """Пересчитывает флаг is_network. Если передан city — только для этой области."""
        if threshold is None:
            threshold = self._get_threshold()

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
                EnrichedCompanyRow.emails,
            )
            if city:
                rows_q = rows_q.filter_by(city=city)

            rows = rows_q.all()
            if not rows:
                logger.info("Нет компаний для анализа сетей.")
                return

            # ── Единый проход: подсчёт доменов/телефонов и кэши нормализации ──
            domain_count: dict[str, int] = {}
            base_domain_count: dict[str, int] = {}
            phone_count: dict[str, int] = {}
            # Cache: row_id -> list of normalized phones (avoids double normalization)
            cached_norm_phones: dict[int, list[str]] = {}
            # Cache: row_id -> extracted domain
            cached_domains: dict[int, str | None] = {}
            # Cache: row_id -> extracted base domain
            cached_base_domains: dict[int, str | None] = {}
            email_domain_count: dict[str, int] = {}
            cached_email_domains: dict[int, list[str]] = {}

            for row_id, website, phones, emails in rows:
                # Domain counting
                domain = extract_domain(website)
                cached_domains[row_id] = domain
                if domain:
                    domain_count[domain] = domain_count.get(domain, 0) + 1

                # Base domain counting (для субдоменных сетей типа *.danila-master.ru)
                base = extract_base_domain(website)
                cached_base_domains[row_id] = base
                if base:
                    base_domain_count[base] = base_domain_count.get(base, 0) + 1

                # Phone counting with normalization cache
                norms: list[str] = []
                for p in phones or []:
                    norm = normalize_phone(p)
                    if norm:
                        norms.append(norm)
                        phone_count[norm] = phone_count.get(norm, 0) + 1
                cached_norm_phones[row_id] = norms

                # Email domain counting
                email_domains: list[str] = []
                for email in (emails or []):
                    if isinstance(email, str) and '@' in email:
                        domain = email.split('@', 1)[1].lower().strip()
                        if domain and domain not in FREE_EMAIL_DOMAINS:
                            email_domains.append(domain)
                            email_domain_count[domain] = email_domain_count.get(domain, 0) + 1
                cached_email_domains[row_id] = email_domains

            network_domains = {d for d, cnt in domain_count.items() if cnt >= threshold}
            network_base_domains = {d for d, cnt in base_domain_count.items() if cnt >= threshold}
            network_phones = {p for p, cnt in phone_count.items() if cnt >= threshold}
            network_email_domains = {d for d, cnt in email_domain_count.items() if cnt >= threshold}

            # Логируем что нашли
            if network_domains:
                for d in sorted(network_domains):
                    logger.debug(f"  Сеть по домену: {d} ({domain_count[d]} компаний)")
            if network_base_domains:
                for d in sorted(network_base_domains):
                    logger.debug(f"  Сеть по base-домену: {d} ({base_domain_count[d]} компаний)")
            if network_phones:
                for p in sorted(network_phones):
                    logger.debug(f"  Сеть по телефону: {p} ({phone_count[p]} компаний)")
            if network_email_domains:
                for d in sorted(network_email_domains):
                    logger.debug(f"  Сеть по email-домену: {d} ({email_domain_count[d]} компаний)")

            if not network_domains and not network_base_domains and not network_phones and not network_email_domains:
                logger.info("Сетей не обнаружено.")
                return

            # ── Применяем флаги — используем кэш вместо повторного вызова ──
            network_ids: list[int] = []
            for row_id, website, phones, emails in rows:
                domain = cached_domains[row_id]
                is_net = domain in network_domains

                # Проверяем base domain если полный домен не попал
                if not is_net:
                    base = cached_base_domains.get(row_id)
                    if base and base in network_base_domains:
                        is_net = True

                if not is_net:
                    for norm in cached_norm_phones[row_id]:
                        if norm in network_phones:
                            is_net = True
                            break

                if not is_net:
                    for ed in cached_email_domains[row_id]:
                        if ed in network_email_domains:
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
                f"(доменов: {len(network_domains)}, "
                f"base-доменов: {len(network_base_domains)}, "
                f"телефонов: {len(network_phones)}, "
                f"email-доменов: {len(network_email_domains)})."
            )

    def find_candidate_groups(
        self, session,
        threshold: int = 2,
        signal_type: str | None = None,
        include_resolved: bool = False,
    ) -> list[dict]:
        """Найти группы кандидатов на сеть/дубль по email-домену, сайту, телефону.

        Args:
            session: SQLAlchemy session.
            threshold: Минимальное кол-во компаний для группы.
            signal_type: Фильтр по типу ('email_domain'|'website'|'phone').
            include_resolved: Включать группы, где все уже помечены is_network.

        Возвращает список групп, где группа = dict с ключами:
        {
            "group_id": str,
            "signal_type": str,
            "signal_value": str,
            "company_count": int,
            "company_ids": list[int],
            "companies": list[dict]
        }
        """
        rows = session.query(
            EnrichedCompanyRow.id,
            EnrichedCompanyRow.name,
            EnrichedCompanyRow.city,
            EnrichedCompanyRow.website,
            EnrichedCompanyRow.phones,
            EnrichedCompanyRow.emails,
        ).all()

        email_domain_map: dict[str, set[int]] = {}
        website_map: dict[str, set[int]] = {}
        phone_map: dict[str, set[int]] = {}
        row_details: dict[int, dict] = {}

        for row_id, name, city, website, phones, emails in rows:
            row_details[row_id] = {
                "id": row_id, "name": name, "city": city,
                "website": website, "phones": phones or [],
                "emails": emails or [],
            }

            if website:
                domain = extract_domain(website)
                if domain:
                    website_map.setdefault(domain, set()).add(row_id)
                base = extract_base_domain(website)
                if base:
                    website_map.setdefault(base, set()).add(row_id)

            for p in (phones or []):
                norm = normalize_phone(p)
                if norm:
                    phone_map.setdefault(norm, set()).add(row_id)

            for email in (emails or []):
                if isinstance(email, str) and '@' in email:
                    domain = email.split('@', 1)[1].lower().strip()
                    if domain and domain not in FREE_EMAIL_DOMAINS:
                        email_domain_map.setdefault(domain, set()).add(row_id)

        # Загружаем is_network для фильтрации уже размеченных
        all_ids: set[int] = set()
        for ids in email_domain_map.values():
            all_ids.update(ids)
        for ids in website_map.values():
            all_ids.update(ids)
        for ids in phone_map.values():
            all_ids.update(ids)

        existing_network: set[int] = set()
        if all_ids and not include_resolved:
            existing_network = {
                r[0] for r in session.query(EnrichedCompanyRow.id).filter(
                    EnrichedCompanyRow.id.in_(list(all_ids)),
                    EnrichedCompanyRow.is_network == True,
                ).all()
            }

        from granite.constants import SPAM_DOMAINS, NON_NETWORK_DOMAINS

        groups = []

        if not signal_type or signal_type == "email_domain":
            for domain, ids in email_domain_map.items():
                if not include_resolved:
                    ids = {i for i in ids if i not in existing_network}
                if len(ids) < threshold:
                    continue
                groups.append({
                    "group_id": f"email:{domain}",
                    "signal_type": "email_domain",
                    "signal_value": domain,
                    "company_count": len(ids),
                    "company_ids": list(ids),
                    "companies": [row_details[i] for i in ids],
                })

        if not signal_type or signal_type == "website":
            for domain, ids in website_map.items():
                if domain in SPAM_DOMAINS or domain in NON_NETWORK_DOMAINS:
                    continue
                if not include_resolved:
                    ids = {i for i in ids if i not in existing_network}
                cities = {row_details[i]["city"] for i in ids}
                if len(cities) < threshold or len(ids) < threshold:
                    continue
                groups.append({
                    "group_id": f"website:{domain}",
                    "signal_type": "website",
                    "signal_value": domain,
                    "company_count": len(ids),
                    "company_ids": list(ids),
                    "companies": [row_details[i] for i in ids],
                })

        if not signal_type or signal_type == "phone":
            for phone, ids in phone_map.items():
                if not include_resolved:
                    ids = {i for i in ids if i not in existing_network}
                cities = {row_details[i]["city"] for i in ids}
                if len(cities) < threshold or len(ids) < threshold:
                    continue
                groups.append({
                    "group_id": f"phone:{phone}",
                    "signal_type": "phone",
                    "signal_value": phone,
                    "company_count": len(ids),
                    "company_ids": list(ids),
                    "companies": [row_details[i] for i in ids],
                })

        return groups
