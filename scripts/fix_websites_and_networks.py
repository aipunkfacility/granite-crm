"""
Одноразовый скрипт: нормализация URL сайтов и глобальная детекция сетей.
Запуск: uv run scripts/fix_websites_and_networks.py
"""
from granite.database import Database
from granite.utils import normalize_website_to_root
from granite.enrichers.network_detector import NetworkDetector
from loguru import logger
import sys

db = Database()

with db.session_scope() as session:
    from granite.database import CompanyRow, EnrichedCompanyRow

    # 1. Нормализация URL в CompanyRow
    rows = session.query(CompanyRow).filter(CompanyRow.website.isnot(None)).all()
    updated = 0
    for row in rows:
        root = normalize_website_to_root(row.website)
        if root and root != row.website:
            logger.debug(f"  FIX URL: {row.website!r} → {root!r}")
            row.website = root
            updated += 1
    logger.info(f"Нормализовано {updated} URL в CompanyRow.")

    # 2. То же самое для EnrichedCompanyRow
    e_rows = session.query(EnrichedCompanyRow).filter(EnrichedCompanyRow.website.isnot(None)).all()
    e_updated = 0
    for row in e_rows:
        root = normalize_website_to_root(row.website)
        if root and root != row.website:
            row.website = root
            e_updated += 1
    logger.info(f"Нормализовано {e_updated} URL в EnrichedCompanyRow.")

# 3. Глобальная пересчёт сетей
logger.info("Запуск глобальной детекции сетей...")
detector = NetworkDetector(db)
detector.scan_for_networks(threshold=2, city=None)

logger.success("Готово! URL нормализованы, сети обновлены.")
