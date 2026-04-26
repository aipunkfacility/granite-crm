# pipeline/checkpoint.py
from granite.database import Database, EnrichedCompanyRow, RawCompanyRow, CompanyRow, CityRefRow
from loguru import logger


class CheckpointManager:
    """Управление стадиями и возобновлением.
    Смотрит в базу и понимает с какого места продолжить.
    """

    def __init__(self, db: Database):
        self.db = db

    def get_stage(self, city: str) -> str:
        """Определить этап для города.
        Возможные стадии: 'start', 'scraped', 'deduped', 'enriched'
        """
        with self.db.session_scope() as session:
            # 1. Сначала проверяем статус в справочнике городов.
            # Если город помечен как успех — он завершён, даже если в нём 0 компаний
            # (например, все были переназначены в другие города).
            city_ref = session.query(CityRefRow).filter_by(name=city).first()
            if city_ref and city_ref.pipeline_status == "success":
                return "enriched"

            # 2. Фолбэк на подсчёт строк (для совместимости и старых данных)
            enriched_count = (
                session.query(EnrichedCompanyRow).filter_by(city=city).count()
            )
            if enriched_count > 0:
                return "enriched"

            dedup_count = session.query(CompanyRow).filter_by(city=city).count()
            if dedup_count > 0:
                return "deduped"

            raw_count = session.query(RawCompanyRow).filter_by(city=city).count()
            if raw_count > 0:
                return "scraped"

            return "start"

    def get_enrichment_progress(self, city: str) -> float:
        """Доля обогащённых компаний для города (0.0 — 1.0).

        Возвращает соотношение COUNT(enriched_companies) / COUNT(companies).
        Используется для возобновления частичного обогащения: если progress < 0.95,
        пайплайн должен дозаполнить оставшиеся компании.
        """
        with self.db.session_scope() as session:
            company_count = session.query(CompanyRow).filter_by(city=city).count()
            if company_count == 0:
                return 0.0
            enriched_count = (
                session.query(EnrichedCompanyRow).filter_by(city=city).count()
            )
            return enriched_count / company_count

    def needs_enrich_resume(self, city: str, threshold: float = 0.95) -> bool:
        """Проверить, нужно ли возобновить обогащение для города.

        Возвращает True если есть компании без enriched-записи
        (progress < threshold). Используется в manager.run_city()
        для автоматического возобновления прерванного обогащения.
        """
        progress = self.get_enrichment_progress(city)
        return 0.0 < progress < threshold

    def clear_city(self, city: str):
        """Полная очистка всех данных по городу (при --force)."""
        with self.db.session_scope() as session:
            session.query(EnrichedCompanyRow).filter_by(city=city).delete()
            session.query(RawCompanyRow).filter_by(city=city).delete()
            session.query(CompanyRow).filter_by(city=city).delete()
            logger.info(f"Очищены все данные для города {city}")
