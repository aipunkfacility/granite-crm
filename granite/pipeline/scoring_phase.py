# pipeline/scoring_phase.py
"""Фаза 5: пересчёт CRM-скоринга и сегментации компаний.

Вынесено из PipelineManager для независимого вызова
(например, при обновлении формулы скоринга без пересбора данных).
"""
from collections import Counter
from granite.database import Database, EnrichedCompanyRow
from loguru import logger
from granite.pipeline.status import print_status


class ScoringPhase:
    """Пересчёт crm_score и segment для enriched-записей города."""

    def __init__(self, db: Database, classifier):
        """
        Args:
            db: экземпляр Database.
            classifier: объект Classifier (enrichers.classifier).
        """
        self.db = db
        self.classifier = classifier

    def run(self, city: str) -> dict[str, int]:
        """Пересчитать скоринг для всех enriched-записей города.

        Returns:
            Словарь {segment: count}, например {"A": 5, "B": 12, "C": 30}.
        """
        print_status("ФАЗА 5: Скоринг и сегментация", "info")
        with self.db.session_scope() as session:
            companies = session.query(EnrichedCompanyRow).filter_by(city=city).all()
            if not companies:
                print_status("Нет данных для скоринга", "warning")
                return {}

            segments = Counter()
            for c in companies:
                d = c.to_dict()
                score = self.classifier.calculate_score(d)
                segment = self.classifier.determine_segment(score)
                c.crm_score = score
                c.segment = segment
                segments[segment] += 1

            summary = ", ".join(f"{seg}: {cnt}" for seg, cnt in sorted(segments.items()))
            print_status(f"Скоринг: {len(companies)} компаний → {summary}", "success")
            return dict(segments)
