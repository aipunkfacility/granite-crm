# pipeline/dedup_phase.py
"""Фаза 2: дедупликация сырых данных из БД.

Вынесено из PipelineManager — полностью независимая фаза
кластеризации и слияния дубликатов.
"""

from typing import Any

from granite.database import Database, RawCompanyRow, CompanyRow, CrmContactRow
from loguru import logger
from granite.pipeline.status import print_status
from granite.pipeline.region_resolver import lookup_region
from granite.utils import normalize_messenger_url, normalize_website_to_root

# Import Dedup
from granite.dedup.phone_cluster import cluster_by_phones
from granite.dedup.site_matcher import cluster_by_site
from granite.dedup.name_matcher import find_name_matches
from granite.dedup.merger import merge_cluster
from granite.dedup.validator import validate_phones, validate_emails


class DedupPhase:
    """Дедупликация: кластеризация по телефону/сайту + слияние."""

    def __init__(self, db: Database, config: dict | None = None):
        self.db = db
        self.config = config or {}

    def run(self, city: str) -> int:
        """Запустить дедупликацию для города.

        Returns:
            Количество уникальных компаний после слияния.
        """
        print_status("ФАЗА 2: Дедупликация и слияние (Dedup)", "info")
        with self.db.session_scope() as session:
            raw_records = session.query(RawCompanyRow).filter_by(city=city).all()
            if not raw_records:
                print_status("Нет данных для дедупликации", "warning")
                return 0

            # Перевод в dict для алгоритмов
            dicts = []
            for r in raw_records:
                # JSON-поля из SQLite могут прийти как строки (не десериализовались)
                phones = r.phones
                if isinstance(phones, str):
                    try:
                        import json
                        phones = json.loads(phones)
                    except (json.JSONDecodeError, ValueError):
                        phones = [phones]
                if not isinstance(phones, list):
                    phones = []

                emails = r.emails
                if isinstance(emails, str):
                    try:
                        import json
                        emails = json.loads(emails)
                    except (json.JSONDecodeError, ValueError):
                        emails = [emails]
                if not isinstance(emails, list):
                    emails = []

                messengers = r.messengers
                if isinstance(messengers, str):
                    try:
                        import json
                        messengers = json.loads(messengers)
                    except (json.JSONDecodeError, ValueError):
                        messengers = {}
                if not isinstance(messengers, dict):
                    messengers = {}

                dicts.append(
                    {
                        "id": r.id,
                        "source": r.source,
                        "source_url": r.source_url or "",
                        "name": r.name,
                        "phones": phones,
                        "address_raw": r.address_raw or "",
                        "website": r.website,
                        "emails": emails,
                        "geo": r.geo,
                        "messengers": messengers,
                        "city": r.city,
                        "needs_review": r.needs_review or False,
                        "review_reason": r.review_reason or "",
                    }
                )

            # Валидация перед кластеризацией
            for d in dicts:
                d["phones"] = validate_phones(d.get("phones", []))
                d["emails"] = validate_emails(d.get("emails", []))

            # Алгоритмы кластеризации (телефон, сайт и имя)
            network_phone_threshold = self.config.get("dedup", {}).get(
                "network_phone_threshold", 10
            )
            clusters_phone = cluster_by_phones(dicts, network_phone_threshold=network_phone_threshold)
            clusters_site = cluster_by_site(dicts)
            name_threshold = self.config.get("dedup", {}).get("name_similarity_threshold", 88)
            clusters_name = find_name_matches(dicts, threshold=name_threshold)

            # Объединение всех кластеров (Union-Find)
            superclusters = self._union_find(dicts, clusters_phone + clusters_site + clusters_name)

            print_status(
                f"Найдено {len(superclusters)} уникальных компаний из {len(dicts)} записей"
            )

            # Слияние и сохранение
            dicts_by_id = {d["id"]: d for d in dicts}
            conflicts = []
            for i, cl in enumerate(superclusters):
                cluster_dicts = [dicts_by_id[cid] for cid in cl]
                merged = merge_cluster(cluster_dicts)

                city_name = merged["city"]
                region_name = lookup_region(city_name)
                
                # FIX: Нормализация ссылок мессенджеров перед сохранением
                messengers = merged.get("messengers", {})
                if messengers:
                    normalized = {}
                    for m_type, m_url in messengers.items():
                        normalized[m_type] = normalize_messenger_url(m_url, m_type)
                    messengers = normalized

                # D3: Validate address — don't save URL as address
                raw_address = merged["address"] or ""
                if raw_address and (raw_address.startswith("http") or raw_address.startswith("www.")):
                    logger.debug(f"D3: отброшен URL-адрес для {merged['name_best']}: {raw_address[:60]}")
                    raw_address = ""

                # FIX: Нормализация URL сайта к корню домена
                raw_website = merged.get("website")
                clean_website = normalize_website_to_root(raw_website) if raw_website else None

                row = CompanyRow(
                    name_best=merged["name_best"],
                    phones=merged["phones"],
                    address=raw_address,
                    website=clean_website,
                    emails=merged["emails"],
                    city=city_name,
                    region=region_name,
                    status="raw",
                    merged_from=merged.get("merged_from", []),
                    messengers=messengers,
                    needs_review=merged.get("needs_review", False),
                    review_reason=merged.get("review_reason", ""),
                )
                session.add(row)
                session.flush()  # Получаем row.id для связей

                # FIX: Создание CRM-контакта для каждой новой компании
                contact = CrmContactRow(
                    company_id=row.id,
                    funnel_stage="new"
                )
                session.add(contact)

                # FIX: Обновление merged_into в исходных raw_companies
                raw_ids = merged.get("merged_from", [])
                if raw_ids:
                    session.query(RawCompanyRow).filter(RawCompanyRow.id.in_(raw_ids)).update(
                        {"merged_into": row.id}, synchronize_session=False
                    )

                # Если регион не найден — записать в unmatched (пропущено для краткости)
                if not region_name:
                    from granite.database import UnmatchedCityRow
                    existing = session.query(UnmatchedCityRow).filter_by(name=city_name).first()
                    if not existing:
                        session.add(UnmatchedCityRow(
                            name=city_name,
                            detected_from="dedup",
                            context=merged["name_best"],
                        ))

                if merged["needs_review"]:
                    conflicts.append(
                        {
                            "cluster_id": i + 1,
                            "records": cluster_dicts,
                            "reason": merged["review_reason"],
                        }
                    )

            if conflicts:
                logger.warning(f"Конфликты при слиянии: {len(conflicts)} компаний")

            return len(superclusters)

    @staticmethod
    def _union_find(
        dicts: list[dict[str, Any]], clusters: list[list[int]]
    ) -> list[list[int]]:
        """Объединение перекрывающихся кластеров через Union-Find.

        Args:
            dicts: список всех записей (нужны только id).
            clusters: список кластеров, каждый — список id записей.

        Returns:
            Список уникальных суперкластеров (списков id).
        """
        id_to_supercluster: dict[int, set[int]] = {}
        for d in dicts:
            id_to_supercluster[d["id"]] = {d["id"]}

        for cl in clusters:
            connected = set()
            for cid in cl:
                connected.update(id_to_supercluster.get(cid, {cid}))
            for cid in connected:
                id_to_supercluster[cid] = connected

        # Уникальные суперкластеры
        seen = set()
        superclusters = []
        for cid, cl in id_to_supercluster.items():
            k = frozenset(cl)
            if k not in seen:
                seen.add(k)
                superclusters.append(list(cl))

        return superclusters
