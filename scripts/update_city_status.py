"""Обновляет status городов в config.yaml на основе данных в БД."""
import yaml
from pathlib import Path
from granite.database import Database

DB_PATH = "data/granite.db"
CONFIG_PATH = "config.yaml"


def main():
    db = Database(db_path=DB_PATH, auto_migrate=False)

    # Считаем записи по городам
    city_counts = {}
    with db.session_scope() as session:
        from sqlalchemy import text
        rows = session.execute(
            text(
                "SELECT city, COUNT(*) as cnt "
                "FROM raw_companies "
                "GROUP BY city"
            )
        ).fetchall()
        for row in rows:
            city_counts[row.city] = row.cnt

    # Читаем config
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Обновляем статусы
    updated = 0
    for city_cfg in config.get("cities", []):
        name = city_cfg.get("name", "")
        if name in city_counts and city_counts[name] > 0:
            if city_cfg.get("status") == "pending":
                city_cfg["status"] = "completed"
                updated += 1
                print(f"  {name}: pending -> completed ({city_counts[name]} records)")

    # Сохраняем
    if updated > 0:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"\nОбновлено {updated} городов")
    else:
        print("\nВсе города актуальны")


if __name__ == "__main__":
    main()
