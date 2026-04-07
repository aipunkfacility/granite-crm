# pipeline/manager.py
"""Лёгкий оркестратор пайплайна обогащения данных.

Рефакторинг: из 807 строк → ~60. Вся бизнес-логика вынесена в отдельные фазы:
  - pipeline/firecrawl_client.py — FirecrawlClient (subprocess CLI)
  - pipeline/region_resolver.py — RegionResolver (конфигурация городов)
  - pipeline/scraping_phase.py   — ScrapingPhase (скрапинг)
  - pipeline/dedup_phase.py      — DedupPhase (дедупликация)
  - pipeline/enrichment_phase.py — EnrichmentPhase (обогащение + firecrawl)
  - pipeline/scoring_phase.py    — ScoringPhase (скоринг + сегментация)
  - pipeline/export_phase.py     — ExportPhase (CSV + пресеты)
"""
from granite.database import Database
from granite.pipeline.checkpoint import CheckpointManager
from granite.pipeline.status import print_status

from granite.enrichers.classifier import Classifier
from granite.enrichers.network_detector import NetworkDetector

from granite.pipeline.firecrawl_client import FirecrawlClient
from granite.pipeline.region_resolver import RegionResolver
from granite.pipeline.scraping_phase import ScrapingPhase
from granite.pipeline.dedup_phase import DedupPhase
from granite.pipeline.enrichment_phase import EnrichmentPhase
from granite.pipeline.scoring_phase import ScoringPhase
from granite.pipeline.export_phase import ExportPhase


class PipelineManager:
    """Оркестрация фаз пайплайна обогащения компаний."""

    def __init__(self, config: dict, db: Database):
        self.config = config
        self.db = db
        self.checkpoints = CheckpointManager(db)

        # Инициализация компонентов
        self.region = RegionResolver(config)
        self.firecrawl = FirecrawlClient(
            timeout=config.get("firecrawl", {}).get("timeout", 60),
            search_limit=config.get("firecrawl", {}).get("search_limit", 3),
        )
        self.scraping = ScrapingPhase(config, db, self.region)
        self.dedup = DedupPhase(db)
        self.enrichment = EnrichmentPhase(config, db, self.firecrawl)
        self.scoring = ScoringPhase(db, Classifier(config))
        self.export = ExportPhase(config, db)
        self.network_detector = NetworkDetector(self.db)

    def run_city(self, city: str, force: bool = False,
                 run_scrapers: bool = True, re_enrich: bool = False):
        """Запуск полного цикла для города (и всех городов этой же области)."""
        print_status(f"Запуск конвейера для: {city}", "bold")

        region_cities = self.region.get_region_cities(city)
        if len(region_cities) > 1:
            print_status(f"Область включает города: {', '.join(region_cities)}", "info")

        if force:
            print_status("Флаг --force: очистка старых данных...", "warning")
            self.checkpoints.clear_city(city)

        # --re-enrich: перескакиваем на обогащение, не трогаем scrape/dedup/enriched
        stage = self.checkpoints.get_stage(city)
        print_status(f"Определен этап старта: {stage}")

        if re_enrich:
            # Пропускаем scrape+dedup, запускаем только точечный поиск (проход 2)
            self.enrichment.run_deep_enrich_existing(city)
        else:
            if stage == "start" and run_scrapers:
                self.scraping.run(city, region_cities)
                stage = "scraped"

            if stage == "scraped":
                self.dedup.run(city)
                stage = "deduped"

            if stage == "deduped":
                self.enrichment.run(city)

        # Пересчёт сетей только для текущего города/области
        print_status("Проверка филиальных сетей...", "info")
        self.network_detector.scan_for_networks(threshold=2, city=city)

        # Пересчет скоринга (т.к. мы обновили is_network)
        self.scoring.run(city)

        # Автоэкспорт
        self.export.run(city)

        print_status(f"Город {city} завершен!", "success")
