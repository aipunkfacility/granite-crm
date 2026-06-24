# enrichers/network_detector.py
from granite.database import Database, EnrichedCompanyRow, CompanyRow, CompanyEmailRow
from loguru import logger
from granite.utils import extract_domain, extract_base_domain, normalize_phone
from granite.constants import FREE_EMAIL_DOMAINS, SPAM_DOMAINS, NON_NETWORK_DOMAINS
from granite.scrapers.web_search import _MULTI_CITY_DOMAIN_CACHE


def _is_ua_region(dom: str | None) -> bool:
    """Проверяет, относится ли домен к украинской зоне (.ua / .укр)."""
    return bool(dom and (dom.endswith('.ua') or dom.endswith('.xn--j1amh')))


class NetworkDetector:
    """Выявляет сети (филиалы одного бизнеса).

    Сеть определяется по двум признакам:
    1. Один и тот же домен сайта у 2+ компаний → сеть.
    2. Один и тот же базовый домен (SLD+TLD) у 2+ компаний → сеть
       (ловит субдоменные сети типа *.danila-master.ru).

    Оптимизация: вместо загрузки всех ORM-объектов в память используются
    лёгкие tuple-запросы (id, website, emails) и массовый UPDATE через IN.
    """

    def __init__(self, db: Database, config: dict | None = None):
        self.db = db
        self.config = config or {}

    def _get_threshold(self) -> int:
        """Порог из конфига или дефолт."""
        return self.config.get("enrichment", {}).get("network_threshold", 2)

    def scan_for_networks(self, threshold: int | None = None, city: str | None = None) -> None:
        """Пересчитывает флаги is_network, network_id и создаёт/обновляет записи в networks."""
        from collections import Counter
        from granite.database import NetworkRow, CompanyRow

        if threshold is None:
            threshold = self._get_threshold()

        with self.db.session_scope() as session:
            # ── 1. Сброс is_network + network_id для целевой области ──
            reset_filter = []
            if city:
                reset_filter.append(EnrichedCompanyRow.city == city)
            session.query(EnrichedCompanyRow).filter(*reset_filter).update(
                {
                    EnrichedCompanyRow.is_network: False,
                    EnrichedCompanyRow.network_id: None,
                },
                synchronize_session=False,
            )
            session.flush()

            # ── 2. Загрузка лёгких tuples + исключение soft-deleted/merged ──
            base_q = session.query(
                EnrichedCompanyRow.id,
                EnrichedCompanyRow.website,
                EnrichedCompanyRow.emails,
                EnrichedCompanyRow.phones,
                EnrichedCompanyRow.name,
                EnrichedCompanyRow.city,
                EnrichedCompanyRow.crm_score,
                EnrichedCompanyRow.segment,
            )
            if city:
                base_q = base_q.filter(EnrichedCompanyRow.city == city)

            rows = base_q.all()
            if not rows:
                logger.info("Нет компаний для анализа сетей.")
                return

            all_ids = [r[0] for r in rows]
            dead_ids: set[int] = set()
            if all_ids:
                dead_q = session.query(CompanyRow.id).filter(
                    CompanyRow.id.in_(all_ids),
                    (CompanyRow.deleted_at.isnot(None)) | (CompanyRow.merged_into.isnot(None)),
                )
                dead_ids = {did for (did,) in dead_q.all()}

            rows = [r for r in rows if r[0] not in dead_ids]
            if not rows:
                logger.info("Нет живых компаний для анализа сетей.")
                return

            # ── 3. Единый проход: подсчёт доменов + кэши ──
            def _is_spam(dom: str | None) -> bool:
                return bool(dom and (dom in SPAM_DOMAINS or dom in NON_NETWORK_DOMAINS or _is_ua_region(dom)))

            domain_count: dict[str, int] = {}
            base_domain_count: dict[str, int] = {}
            cached_domains: dict[int, str | None] = {}
            cached_base_domains: dict[int, str | None] = {}

            for row_id, website, *_ in rows:
                domain = extract_domain(website)
                cached_domains[row_id] = domain
                if domain and not _is_spam(domain):
                    domain_count[domain] = domain_count.get(domain, 0) + 1

                base = extract_base_domain(website)
                cached_base_domains[row_id] = base
                if base and not _is_spam(base):
                    base_domain_count[base] = base_domain_count.get(base, 0) + 1

            network_domains = {d for d, cnt in domain_count.items() if cnt >= threshold}
            network_base_domains = {d for d, cnt in base_domain_count.items() if cnt >= threshold}

            if not network_domains and not network_base_domains:
                logger.info("Сетей не обнаружено.")
                return

            for d in sorted(network_domains):
                logger.debug(f"  Сеть по домену: {d} ({domain_count[d]} компаний)")
            for d in sorted(network_base_domains):
                logger.debug(f"  Сеть по base-домену: {d} ({base_domain_count[d]} компаний)")

            # ── 4. Группировка компаний по base_domain ──
            # row_data: id -> (website, emails, phones, name, city, score, segment)
            row_data: dict[int, tuple] = {r[0]: r[1:] for r in rows}

            # base_domain -> set of company ids
            groups: dict[str, set[int]] = {}
            for row_id in row_data:
                base = cached_base_domains.get(row_id)
                if base and not _is_spam(base) and base in network_base_domains:
                    groups.setdefault(base, set()).add(row_id)

            # ── 5. UPSERT в networks + SET network_id ──
            network_count = 0
            member_count = 0

            for base_domain, member_ids in groups.items():
                if len(member_ids) < threshold:
                    continue

                companies_data = [row_data[mid] for mid in member_ids]
                emails_all: set[str] = set()
                phones_all: set[str] = set()
                subdomains: set[str] = set()
                cities: set[str] = set()
                names: list[str] = []
                segments: list[str] = []
                scores: list[float] = []

                for mid in member_ids:
                    website, emails, phones, name, city_name, score, segment = row_data[mid]
                    dom = extract_domain(website)
                    if dom:
                        subdomains.add(dom)
                    for e in (emails or []):
                        if isinstance(e, str) and "@" in e:
                            emails_all.add(e)
                    for p in (phones or []):
                        norm = normalize_phone(p)
                        if norm:
                            phones_all.add(norm)
                    cities.add(city_name)
                    names.append(name or "")
                    segments.append(segment or "D")
                    scores.append(score or 0.0)

                seg_dist = dict(Counter(segments).most_common())
                most_common_name = Counter(names).most_common(1)[0][0] if names else base_domain
                avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
                classify_dicts = [
                    {"city": rd[4], "emails": rd[2] or []}
                    for rd in companies_data
                ]
                ntype = self._classify_network_type(classify_dicts, "website")

                existing = session.query(NetworkRow).filter_by(base_domain=base_domain).first()
                if existing:
                    existing.name = most_common_name
                    existing.network_type = ntype
                    existing.subdomains = sorted(subdomains)
                    existing.emails = sorted(emails_all)
                    existing.phones = sorted(phones_all)
                    existing.company_count = len(member_ids)
                    existing.city_count = len(cities)
                    existing.cities = sorted(cities)
                    existing.avg_score = avg_score
                    existing.segment_dist = seg_dist
                    network_row = existing
                else:
                    network_row = NetworkRow(
                        name=most_common_name,
                        base_domain=base_domain,
                        signal_type="website",
                        network_type=ntype,
                        subdomains=sorted(subdomains),
                        emails=sorted(emails_all),
                        phones=sorted(phones_all),
                        company_count=len(member_ids),
                        city_count=len(cities),
                        cities=sorted(cities),
                        avg_score=avg_score,
                        segment_dist=seg_dist,
                    )
                    session.add(network_row)
                    session.flush()

                network_count += 1

                # Chunked UPDATE of EnrichedCompanyRow
                member_list = list(member_ids)
                chunk_size = 500
                for i in range(0, len(member_list), chunk_size):
                    chunk = member_list[i : i + chunk_size]
                    session.query(EnrichedCompanyRow).filter(
                        EnrichedCompanyRow.id.in_(chunk)
                    ).update(
                        {
                            EnrichedCompanyRow.is_network: True,
                            EnrichedCompanyRow.network_id: network_row.id,
                        },
                        synchronize_session=False,
                    )
                member_count += len(member_ids)

            logger.info(
                f"Обнаружено {member_count} филиалов сетей "
                f"(сетей: {network_count})."
            )

    def propagate_shared_contacts(self) -> int:
        """Propagate shared emails among network members.

        After scan_for_networks() has set is_network=True, this method
        groups network companies by shared domain / email-domain and
        copies network-common emails to members that are missing them.

        Only propagates emails whose domain matches the group signal
        (e.g., @guravli.agency for an email-domain group). Free email
        domains (mail.ru, gmail.com, etc.) are never propagated.

        Writes to CompanyRow.emails, EnrichedCompanyRow.emails,
        and CompanyEmailRow (via sync_company_emails).

        Returns:
            Number of companies that received new emails.
        """
        from granite.email.sync import sync_company_emails

        affected = 0
        with self.db.session_scope() as session:
            rows = session.query(
                EnrichedCompanyRow.id,
                EnrichedCompanyRow.website,
                EnrichedCompanyRow.emails,
            ).filter(
                EnrichedCompanyRow.is_network == True,
            ).all()

            if not rows:
                logger.info("Нет сетевых компаний — пропагация не нужна.")
                return 0

            domain_groups: dict[str, set[int]] = {}
            row_email_map: dict[int, set[str]] = {}

            for row_id, website, emails in rows:
                row_set = set()
                for e in (emails or []):
                    if isinstance(e, str) and '@' in e:
                        row_set.add(e.strip())
                row_email_map[row_id] = row_set

                if website:
                    dom = extract_domain(website)
                    if dom and dom not in SPAM_DOMAINS and dom not in NON_NETWORK_DOMAINS:
                        domain_groups.setdefault(dom, set()).add(row_id)
                    base = extract_base_domain(website)
                    if base and base not in SPAM_DOMAINS and base not in NON_NETWORK_DOMAINS:
                        domain_groups.setdefault(base, set()).add(row_id)

            all_groups = [
                ("domain", ids) for _, ids in domain_groups.items()
            ]

            for group_type, member_ids in all_groups:
                if len(member_ids) < 2:
                    continue
                group_emails: set[str] = set()
                for rid in member_ids:
                    group_emails.update(row_email_map.get(rid, set()))
                if not group_emails:
                    continue

                for rid in member_ids:
                    company = session.get(CompanyRow, rid)
                    enriched = session.get(EnrichedCompanyRow, rid)
                    if not company or not enriched:
                        continue

                    existing = set(company.emails or [])
                    missing = group_emails - existing
                    if not missing:
                        continue

                    new_emails = sorted(existing | missing)
                    company.emails = new_emails
                    enriched.emails = new_emails
                    sync_company_emails(session, rid, new_emails)
                    affected += 1
                    logger.info(
                        f"Пропагация: {company.name_best or '?'} "
                        f"({company.city}) — добавлено {len(missing)} email"
                    )

            session.flush()
            logger.info(f"Пропагация: обновлено {affected} компаний")
        return affected

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
            # Pre-compute which base_domains are already known major networks (3+ cities)
            # to avoid duplicating subdomains as separate groups (e.g. ntagil.danila-master.ru)
            base_network_cities: dict[str, set[str]] = {}
            for domain_key, ids_set in website_map.items():
                pk = domain_key.split(".")
                if len(pk) < 3:
                    continue  # not a subdomain, skip
                base = ".".join(pk[-2:])
                base_ids = {i for i in website_map.get(base, set())
                            if row_details[i].get("segment") != "spam"}
                if len(base_ids) < 3:
                    continue
                base_cities = {row_details[i]["city"] for i in base_ids}
                if len(base_cities) >= 3:
                    base_network_cities[domain_key] = base_cities

            for domain, ids in website_map.items():
                if domain in SPAM_DOMAINS or domain in NON_NETWORK_DOMAINS or _is_ua_region(domain):
                    continue
                parts = domain.split(".")
                if len(parts) >= 2:
                    sld_tld = ".".join(parts[-2:])
                    if sld_tld in SPAM_DOMAINS or sld_tld in NON_NETWORK_DOMAINS or _is_ua_region(sld_tld):
                        continue
                # Skip subdomains of known major networks (Данила-Мастер и т.п.)
                if domain in base_network_cities:
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

        if not signal_type or signal_type == "email_domain":
            for domain, ids in email_domain_map.items():
                if _is_ua_region(domain):
                    continue
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
                if _is_ua_region(domain):
                    continue
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
            # Pre-compute which base_domains are already known major networks
            base_network_cities: dict[str, set[str]] = {}
            for domain_key, ids_set in website_map.items():
                pk = domain_key.split(".")
                if len(pk) < 3:
                    continue
                base = ".".join(pk[-2:])
                base_ids = {i for i in website_map.get(base, set())
                            if row_details[i].get("segment") != "spam"}
                if len(base_ids) < 3:
                    continue
                base_cities = {row_details[i]["city"] for i in base_ids}
                if len(base_cities) >= 3:
                    base_network_cities[domain_key] = base_cities

            for domain, ids in website_map.items():
                if domain in SPAM_DOMAINS or domain in NON_NETWORK_DOMAINS or _is_ua_region(domain):
                    continue
                parts = domain.split(".")
                if len(parts) >= 2:
                    sld_tld = ".".join(parts[-2:])
                    if sld_tld in SPAM_DOMAINS or sld_tld in NON_NETWORK_DOMAINS or _is_ua_region(sld_tld):
                        continue
                if domain in base_network_cities:
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

        return groups
