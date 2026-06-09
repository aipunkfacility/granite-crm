# enrichers/network_detector.py
from granite.database import Database, EnrichedCompanyRow, CompanyRow
from loguru import logger
from granite.utils import extract_domain, extract_base_domain, normalize_phone
from granite.constants import FREE_EMAIL_DOMAINS, SPAM_DOMAINS, NON_NETWORK_DOMAINS
from granite.scrapers.web_search import _MULTI_CITY_DOMAIN_CACHE


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
                if domain and domain not in SPAM_DOMAINS and domain not in NON_NETWORK_DOMAINS:
                    domain_count[domain] = domain_count.get(domain, 0) + 1

                # Base domain counting (для субдоменных сетей типа *.danila-master.ru)
                base = extract_base_domain(website)
                cached_base_domains[row_id] = base
                if base and base not in SPAM_DOMAINS and base not in NON_NETWORK_DOMAINS:
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

    @staticmethod
    def _classify_network_type(
        companies: list[dict],
        signal_type: str,
        threshold: float = 0.7,
    ) -> str:
        if not companies:
            return "regional"

        cities = set(c["city"] for c in companies if c.get("city"))
        if len(cities) <= 1:
            return "local"

        from collections import Counter
        email_counter: Counter[str] = Counter()
        for c in companies:
            for e in (c.get("emails") or []):
                if isinstance(e, str) and "@" in e:
                    email_counter[e] += 1

        if email_counter:
            total_with_email = sum(email_counter.values())
            most_common_count = email_counter.most_common(1)[0][1]
            if total_with_email >= 2 and most_common_count >= total_with_email * threshold:
                return "regional"

        if signal_type in ("phone", "email_domain"):
            return "aggregator"

        return "franchise"

    def list_networks(
        self, session,
        signal_type: str | None = None,
        min_company_count: int = 2,
        network_type: str | None = None,
        contact_status: str | None = None,
    ) -> list[dict]:
        rows = session.query(
            EnrichedCompanyRow.id,
            EnrichedCompanyRow.name,
            EnrichedCompanyRow.city,
            EnrichedCompanyRow.website,
            EnrichedCompanyRow.phones,
            EnrichedCompanyRow.emails,
            EnrichedCompanyRow.crm_score,
            EnrichedCompanyRow.segment,
        ).filter(
            EnrichedCompanyRow.is_network == True,
        ).all()

        from collections import Counter
        from granite.constants import SPAM_DOMAINS, NON_NETWORK_DOMAINS

        website_map: dict[str, set[int]] = {}
        phone_map: dict[str, set[int]] = {}
        email_domain_map: dict[str, set[int]] = {}
        row_details: dict[int, dict] = {}

        for row_id, name, city, website, phones, emails, score, segment in rows:
            row_details[row_id] = {
                "id": row_id, "name": name, "city": city,
                "website": website, "phones": phones or [],
                "emails": emails or [], "score": score or 0.0,
                "segment": segment or "D",
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

        # Exclude soft-deleted and merged companies from all maps
        dead_ids_result = session.query(CompanyRow.id).filter(
            CompanyRow.id.in_(list(row_details.keys())),
            (CompanyRow.deleted_at.isnot(None)) | (CompanyRow.merged_into.isnot(None)),
        ).all()
        dead_ids = {d_id for (d_id,) in dead_ids_result}
        for dead_id in dead_ids:
            row_details.pop(dead_id, None)
        for m in (website_map, phone_map, email_domain_map):
            for key in list(m.keys()):
                m[key] -= dead_ids
                if not m[key]:
                    del m[key]

        from granite.database import CrmEmailLogRow

        all_company_ids: set[int] = set()
        if not signal_type or signal_type == "website":
            for ids in website_map.values():
                all_company_ids.update(ids)
        if not signal_type or signal_type == "phone":
            for ids in phone_map.values():
                all_company_ids.update(ids)
        if not signal_type or signal_type == "email_domain":
            for ids in email_domain_map.values():
                all_company_ids.update(ids)

        contacted_company_ids: set[int] = set()
        if all_company_ids:
            logs = session.query(
                CrmEmailLogRow.company_id,
            ).filter(
                CrmEmailLogRow.company_id.in_(list(all_company_ids)),
            ).distinct().all()
            contacted_company_ids = {cid for (cid,) in logs}

        def _group_email_and_segment(ids_set: set[int]) -> tuple:
            email_counter: Counter[str] = Counter()
            segment_counter: Counter[str] = Counter()
            for row_id in ids_set:
                for e in (row_details[row_id].get("emails") or []):
                    if isinstance(e, str) and "@" in e:
                        email_counter[e] += 1
                seg = row_details[row_id].get("segment", "D")
                segment_counter[seg] += 1
            primary_email = email_counter.most_common(1)[0][0] if email_counter else None
            return primary_email, dict(segment_counter.most_common())

        groups = []

        if not signal_type or signal_type == "website":
            for domain, ids in website_map.items():
                if domain in SPAM_DOMAINS or domain in NON_NETWORK_DOMAINS:
                    continue
                parts = domain.split(".")
                if len(parts) >= 2:
                    sld_tld = ".".join(parts[-2:])
                    if sld_tld in SPAM_DOMAINS or sld_tld in NON_NETWORK_DOMAINS:
                        continue
                ids = {i for i in ids if row_details[i].get("segment") != "spam"}
                if len(ids) < min_company_count:
                    continue
                cities = Counter(row_details[i]["city"] for i in ids)
                scores = [row_details[i]["score"] for i in ids]
                companies_data = [row_details[i] for i in ids]
                ntype = self._classify_network_type(companies_data, "website")
                # Override: если домен (или его base) известен как агрегатор
                if ntype != "aggregator":
                    parts = domain.split(".")
                    bare_base = ".".join(parts[-2:]) if len(parts) >= 2 else domain
                    for cached_domain in _MULTI_CITY_DOMAIN_CACHE:
                        if cached_domain == bare_base or cached_domain.endswith("." + bare_base):
                            ntype = "aggregator"
                            break
                email_count = sum(1 for i in ids if row_details[i]["emails"])
                phone_count = sum(1 for i in ids if row_details[i]["phones"])
                primary_email, segment_dist = _group_email_and_segment(ids)
                group_contacted = contacted_company_ids & ids
                groups.append({
                    "group_id": f"website:{domain}",
                    "signal_type": "website",
                    "signal_value": domain,
                    "company_count": len(ids),
                    "city_count": len(cities),
                    "avg_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
                    "email_count": email_count,
                    "phone_count": phone_count,
                    "top_cities": [{"name": c, "count": n} for c, n in cities.most_common(10)],
                    "network_type": ntype,
                    "primary_email": primary_email,
                    "segment_dist": segment_dist,
                    "contact_status": "sent" if group_contacted else "none",
                    "sent_count": len(group_contacted),
                    "total_count": len(ids),
                })

        if not signal_type or signal_type == "phone":
            for phone, ids in phone_map.items():
                ids = {i for i in ids if row_details[i].get("segment") != "spam"}
                if len(ids) < min_company_count:
                    continue
                cities = Counter(row_details[i]["city"] for i in ids)
                if len(cities) < 2:
                    continue
                scores = [row_details[i]["score"] for i in ids]
                companies_data = [row_details[i] for i in ids]
                ntype = self._classify_network_type(companies_data, "phone")
                primary_email, segment_dist = _group_email_and_segment(ids)
                group_contacted = contacted_company_ids & ids
                groups.append({
                    "group_id": f"phone:{phone}",
                    "signal_type": "phone",
                    "signal_value": phone,
                    "company_count": len(ids),
                    "city_count": len(cities),
                    "avg_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
                    "email_count": sum(1 for i in ids if row_details[i]["emails"]),
                    "phone_count": len(ids),
                    "top_cities": [{"name": c, "count": n} for c, n in cities.most_common(10)],
                    "network_type": ntype,
                    "primary_email": primary_email,
                    "segment_dist": segment_dist,
                    "contact_status": "sent" if group_contacted else "none",
                    "sent_count": len(group_contacted),
                    "total_count": len(ids),
                })

        if not signal_type or signal_type == "email_domain":
            for domain, ids in email_domain_map.items():
                ids = {i for i in ids if row_details[i].get("segment") != "spam"}
                if len(ids) < min_company_count:
                    continue
                cities = Counter(row_details[i]["city"] for i in ids)
                scores = [row_details[i]["score"] for i in ids]
                companies_data = [row_details[i] for i in ids]
                ntype = self._classify_network_type(companies_data, "email_domain")
                primary_email, segment_dist = _group_email_and_segment(ids)
                group_contacted = contacted_company_ids & ids
                groups.append({
                    "group_id": f"email:{domain}",
                    "signal_type": "email_domain",
                    "signal_value": domain,
                    "company_count": len(ids),
                    "city_count": len(cities),
                    "avg_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
                    "email_count": len(ids),
                    "phone_count": sum(1 for i in ids if row_details[i]["phones"]),
                    "top_cities": [{"name": c, "count": n} for c, n in cities.most_common(10)],
                    "network_type": ntype,
                    "primary_email": primary_email,
                    "segment_dist": segment_dist,
                    "contact_status": "sent" if group_contacted else "none",
                    "sent_count": len(group_contacted),
                    "total_count": len(ids),
                })

        if network_type:
            groups = [g for g in groups if g.get("network_type") == network_type]
        if contact_status:
            groups = [g for g in groups if g.get("contact_status") == contact_status]
        return groups

    def get_network_detail(
        self, session,
        group_id: str,
    ) -> dict | None:
        parts = group_id.split(":", 1)
        if len(parts) != 2:
            return None
        prefix, signal_value = parts

        SIGNAL_TYPE_MAP = {"website": "website", "phone": "phone", "email": "email_domain"}
        signal_type = SIGNAL_TYPE_MAP.get(prefix)
        if signal_type is None:
            return None

        all_networks = self.list_networks(session, signal_type=signal_type, min_company_count=1)
        match = None
        for n in all_networks:
            if n["group_id"] == group_id:
                match = n
                break

        if not match:
            return None

        rows = session.query(
            EnrichedCompanyRow.id,
            EnrichedCompanyRow.name,
            EnrichedCompanyRow.city,
            EnrichedCompanyRow.website,
            EnrichedCompanyRow.phones,
            EnrichedCompanyRow.emails,
            EnrichedCompanyRow.crm_score,
            EnrichedCompanyRow.segment,
        ).filter(
            EnrichedCompanyRow.is_network == True,
        ).all()

        query_val = signal_value.lower()
        company_ids: set[int] = set()

        for row_id, name, city, website, phones, emails, score, segment in rows:
            if segment == "spam":
                continue
            include = False
            if signal_type == "website":
                d = extract_domain(website)
                b = extract_base_domain(website)
                include = (d and d == query_val) or (b and b == query_val)
            elif signal_type == "phone":
                for p in (phones or []):
                    norm = normalize_phone(p)
                    if norm and norm == query_val:
                        include = True
                        break
            elif signal_type == "email_domain":
                for email in (emails or []):
                    if isinstance(email, str) and '@' in email:
                        domain = email.split('@', 1)[1].lower().strip()
                        if domain == query_val:
                            include = True
                            break
            if include:
                company_ids.add(row_id)

        # Exclude soft-deleted and merged companies
        if company_ids:
            dead_rows = session.query(CompanyRow.id).filter(
                CompanyRow.id.in_(list(company_ids)),
                (CompanyRow.deleted_at.isnot(None)) | (CompanyRow.merged_into.isnot(None)),
            ).all()
            company_ids -= {dead_id for (dead_id,) in dead_rows}

        match["companies"] = [{
            "id": row_id,
            "name": name,
            "city": city,
            "website": website,
            "phones": phones or [],
            "emails": emails or [],
            "score": score or 0.0,
        } for row_id, name, city, website, phones, emails, score, segment in rows if row_id in company_ids]

        return match

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
            EnrichedCompanyRow.is_network,
        ).all()

        email_domain_map: dict[str, set[int]] = {}
        website_map: dict[str, set[int]] = {}
        phone_map: dict[str, set[int]] = {}
        row_details: dict[int, dict] = {}

        for row_id, name, city, website, phones, emails, is_network in rows:
            row_details[row_id] = {
                "id": row_id, "name": name, "city": city,
                "website": website, "phones": phones or [],
                "emails": emails or [],
                "is_network": is_network or False,
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
                all_marked = all(row_details[i]["is_network"] for i in ids)
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
                    "all_marked": all_marked,
                })

        if not signal_type or signal_type == "website":
            for domain, ids in website_map.items():
                if domain in SPAM_DOMAINS or domain in NON_NETWORK_DOMAINS:
                    continue
                parts = domain.split(".")
                if len(parts) >= 2:
                    sld_tld = ".".join(parts[-2:])
                    if sld_tld in SPAM_DOMAINS or sld_tld in NON_NETWORK_DOMAINS:
                        continue
                all_marked = all(row_details[i]["is_network"] for i in ids)
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
                    "all_marked": all_marked,
                })

        if not signal_type or signal_type == "phone":
            for phone, ids in phone_map.items():
                all_marked = all(row_details[i]["is_network"] for i in ids)
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
                    "all_marked": all_marked,
                })

        return groups
