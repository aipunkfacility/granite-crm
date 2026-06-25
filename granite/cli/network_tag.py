# granite/cli/network_tag.py
"""CLI-команда для сканирования сетей и заполнения таблицы networks."""
from granite.database import Database
from granite.enrichers.network_detector import NetworkDetector


def run_tag_networks(threshold: int = 2, city: str | None = None):
    """Запустить scan_for_networks() для заполнения таблицы networks."""
    db = Database()
    detector = NetworkDetector(db)
    detector.scan_for_networks(threshold=threshold, city=city)

    from granite.database import NetworkRow
    with db.session_scope() as session:
        count = session.query(NetworkRow).count()
        print(f"Готово. Создано/обновлено сетей: {count}")
