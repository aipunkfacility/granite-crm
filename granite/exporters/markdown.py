# exporters/markdown.py
import os
from granite.database import Database, EnrichedCompanyRow
from loguru import logger
from granite.exporters.csv import _apply_preset_filter


def _escape_md(text: str) -> str:
    """Экранирование pipe-символов для markdown-таблиц."""
    return text.replace("|", "\\|") if text else ""


def _group_by_segment(records):
    """Группировка записей по сегментам A/B/C/D."""
    segments = {"A": [], "B": [], "C": [], "D": []}
    for r in records:
        seg = r.segment or "D"
        if seg in segments:
            segments[seg].append(r)
        else:
            segments["D"].append(r)
    return segments


def _write_segment_table(f, seg_label: str, seg_records: list):
    """Запись таблицы сегмента в markdown-файл."""
    if not seg_records:
        return
    f.write(f"## Сегмент {seg_label} ({len(seg_records)} шт.)\n\n")
    f.write("| Название | Телефон | Сайт | Telegram | CMS | Score |\n")
    f.write("|----------|---------|------|----------|-----|-------|\n")

    for r in sorted(seg_records, key=lambda x: x.crm_score, reverse=True):
        d = r.to_dict()
        phones = "<br>".join(d.get("phones", []))
        site = f"[Сайт]({d['website']})" if d.get("website") else "-"

        tg = d.get("messengers", {}).get("telegram")
        tg_link = f"[TG]({tg})" if tg else "-"

        name = _escape_md(d["name"])
        f.write(f"| **{name}** | {phones} | {site} | {tg_link} | {d.get('cms', '-')} | {d.get('crm_score', 0)} |\n")

    f.write("\n")


class MarkdownExporter:
    """Генератор Markdown-отчетов для Notion/Obsidian."""

    def __init__(self, db: Database, output_dir: str = "data/export"):
        self.db = db
        self.output_dir = output_dir

    def export_city(self, city: str):
        session = self.db.get_session()
        try:
            records = session.query(EnrichedCompanyRow).filter_by(city=city).all()
            if not records:
                return

            os.makedirs(self.output_dir, exist_ok=True)
            filepath = os.path.join(self.output_dir, f"{city.lower()}_report.md")

            segments = _group_by_segment(records)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# База мастерских: {city.capitalize()}\n\n")
                f.write(f"**Всего компаний:** {len(records)}\n\n")

                for seg in ["A", "B", "C", "D"]:
                    _write_segment_table(f, seg, segments[seg])

            logger.info(f"Экспорт Markdown завершен: {filepath}")
        finally:
            session.close()

    def export_city_with_preset(self, city: str, preset_name: str, preset: dict):
        """Экспорт города с фильтром из пресета config.yaml."""
        session = self.db.get_session()
        try:
            query = session.query(EnrichedCompanyRow).filter_by(city=city)
            query = _apply_preset_filter(query, preset_name, preset)
            records = query.all()

            if not records:
                logger.warning(f"Нет данных для экспорта {city} с пресетом '{preset_name}' (markdown)")
                return

            os.makedirs(self.output_dir, exist_ok=True)
            filepath = os.path.join(self.output_dir, f"{city.lower()}_{preset_name}.md")

            description = preset.get("description", "")
            segments = _group_by_segment(records)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# База мастерских: {city.capitalize()} — {preset_name}\n\n")
                if description:
                    f.write(f"**Фильтр:** {description}\n\n")
                f.write(f"**Всего компаний:** {len(records)}\n\n")

                for seg in ["A", "B", "C", "D"]:
                    _write_segment_table(f, seg, segments[seg])

            logger.info(f"Экспорт Markdown (пресет '{preset_name}'): {filepath} ({len(records)} записей)")
        finally:
            session.close()
