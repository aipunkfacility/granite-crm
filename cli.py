# cli.py
import typer
import yaml
import sys
import os
from pathlib import Path
from loguru import logger
from granite.database import Database
from granite.pipeline.manager import PipelineManager, PipelineCriticalError
from granite.exporters.csv import CsvExporter
from granite.exporters.markdown import MarkdownExporter
from granite.config_validator import validate_config as _validate_config
from granite.pipeline.status import print_status
from granite.dedup.network_filter import detect_and_mark_aggregators

app = typer.Typer(help="Granite Workshops DB - Сбор и обогащение базы ритуальных мастерских")

# Global state for --config
_config_path: str = "config.yaml"

def config_callback(value: str):
    global _config_path
    _config_path = value

@app.callback()
def main(config: str = typer.Option("config.yaml", "--config", "-c", help="Путь к config.yaml", callback=config_callback)):
    """Granite Workshops DB — pipeline для сбора и обогащения базы."""
    pass

def setup_logging(config: dict):
    """Настройка логирования из config.yaml."""
    logger.remove()  # убираем дефолтный handler
    log_cfg = config.get("logging", {})
    level = log_cfg.get("level", "INFO")
    fmt = log_cfg.get("format", "{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}")
    rotation = log_cfg.get("rotation", "10 MB")
    retention = log_cfg.get("retention", "30 days")

    # Консоль
    logger.add(sys.stderr, level=level, format=fmt, colorize=True)
    # Файл
    os.makedirs("data/logs", exist_ok=True)
    logger.add("data/logs/granite.log", level=level, format=fmt,
               rotation=rotation, retention=retention, encoding="utf-8")

def load_config(config_path: str | None = None):
    path = config_path or _config_path
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print_status(f"Ошибка: файл конфигурации не найден: {path}", "error")
        raise typer.Exit(1)
    except yaml.YAMLError as e:
        print_status(f"Ошибка: некорректный YAML в файле конфигурации: {e}", "error")
        raise typer.Exit(1)

    if not _validate_config(config):
        print_status("Ошибка: конфигурация не прошла валидацию (см. выше)", "error")
        raise typer.Exit(1)
    return config


@app.command()
def run(
    city: str = typer.Argument(..., help="Название города, например 'Астрахань' или 'all' для всех"),
    force: bool = typer.Option(False, "--force", "-f", help="Очистить старые данные и начать заново"),
    no_scrape: bool = typer.Option(False, "--no-scrape", help="Пропустить фазу парсинга (использовать кэш)"),
    re_enrich: bool = typer.Option(False, "--re-enrich", help="Перезапустить только обогащение (сохранить scrape+dedup)"),
    resume: bool = typer.Option(False, "--resume", "-r", help="Пропустить завершённые города, продолжить с места остановки"),
    city_list: Path = typer.Option(None, "--city-list", "-l",
        help="Файл со списком городов (по одному на строку)"),
):
    """Запуск полного цикла сбора, дедупликации и обогащения для города."""
    config = load_config()
    setup_logging(config)
    db = Database(config_path=_config_path)
    
    manager = PipelineManager(config, db)
    
    target_cities = []
    if city_list:
        # 1.5: Batch-запуск из файла
        if not city_list.exists():
            print_status(f"Файл не найден: {city_list}", "error")
            raise typer.Exit(1)
        cities_from_file = city_list.read_text(encoding="utf-8").strip().splitlines()
        cities_from_file = [c.strip() for c in cities_from_file if c.strip() and not c.strip().startswith("#")]
        if not cities_from_file:
            print_status("Файл со списком городов пуст", "error")
            raise typer.Exit(1)
        target_cities = cities_from_file
        print_status(f"Загружено {len(target_cities)} городов из {city_list}", "info")
    elif city.lower() == "all":
        # Все города из data/regions.yaml
        from granite.pipeline.region_resolver import RegionResolver
        resolver = RegionResolver(config)
        target_cities = resolver.get_all_cities()
        print_status(f"Всего городов в regions.yaml: {len(target_cities)}", "info")
    else:
        target_cities = [city]

    # Задержка между городами для предотвращения rate-limit (429).
    # Настраивается через config: scraping.inter_city_delay (секунды, 0 = без паузы).
    import time
    inter_city_delay = config.get("scraping", {}).get("inter_city_delay", 2)

    # --resume: пропустить города, которые уже полностью обработаны,
    # и начать с первого незавершённого.
    if resume:
        original_count = len(target_cities)
        remaining = []
        for c in target_cities:
            stage = manager.checkpoints.get_stage(c)
            if stage == "enriched" and not manager.checkpoints.needs_enrich_resume(c):
                continue  # полностью готово — пропускаем
            remaining.append(c)
        skipped = original_count - len(remaining)
        if skipped > 0:
            print_status(f"--resume: пропускаю {skipped} завершённых городов, остаётся {len(remaining)}", "info")
        target_cities = remaining
        if not target_cities:
            print_status("Все города уже обработаны — нечего делать", "success")
            db.engine.dispose()
            return

    # Счётчик реально обработанных городов (для паузы только между ними)
    processed_count = 0
    skipped_count = 0
    total = len(target_cities)

    for i, c in enumerate(target_cities):
        try:
            result = manager.run_city(
                c, force=force, run_scrapers=not no_scrape, re_enrich=re_enrich,
                quiet_skip=True,
            )
            if result is False:
                # Город пропущен (уже обработан)
                skipped_count += 1
                continue

            processed_count += 1
            # Пауза только между реально обработанными городами
            if processed_count > 0 and inter_city_delay > 0 and i < total - 1:
                print_status(
                    f"Пауза {inter_city_delay}с перед следующим городом ({i+1}/{total})",
                    "info",
                )
                time.sleep(inter_city_delay)
        except PipelineCriticalError:
            print_status(f"Критическая ошибка для города {c}. Остановка.", "error")
            raise typer.Exit(1)

    print_status(f"Готово: обработано {processed_count}, пропущено {skipped_count}", "success")
    db.engine.dispose()

@app.command()
def export(
    city: str = typer.Argument(..., help="Название города или 'all'"),
    fmt: str = typer.Option("csv", "--format", "-f", help="Формат экспорта: csv или md")
):
    """Экспорт готовых данных из БД."""
    config = load_config()
    setup_logging(config)
    db = Database(config_path=_config_path)

    target_cities = []
    if city.lower() == "all":
        from granite.pipeline.region_resolver import RegionResolver
        resolver = RegionResolver(config)
        target_cities = resolver.get_all_cities()
    else:
        target_cities = [city]

    for c in target_cities:
        if fmt == "csv":
            exporter = CsvExporter(db)
        else:
            exporter = MarkdownExporter(db)
        exporter.export_city(c)

    print_status("Экспорт завершен успешно!", "success")
    db.engine.dispose()

@app.command()
def export_preset(
    city: str = typer.Argument(..., help="Название города или 'all'"),
    preset: str = typer.Argument(..., help="Имя пресета из config.yaml (hot_leads, producers_only, ...)"),
):
    """Экспорт данных по пресету из config.yaml."""
    config = load_config()
    setup_logging(config)
    db = Database(config_path=_config_path)

    export_presets = config.get("export_presets", {})
    if not export_presets:
        print_status("В config.yaml нет секции export_presets", "warning")
        raise typer.Exit(1)

    if preset not in export_presets:
        available = ", ".join(export_presets.keys())
        print_status(f"Пресет '{preset}' не найден. Доступные: {available}", "warning")
        raise typer.Exit(1)

    preset_config = export_presets[preset]
    preset_format = preset_config.get("format", "csv")
    description = preset_config.get("description", "")

    print_status(f"Экспорт пресета '{preset}': {description}", "info")

    target_cities = []
    if city.lower() == "all":
        from granite.pipeline.region_resolver import RegionResolver
        resolver = RegionResolver(config)
        target_cities = resolver.get_all_cities()
    else:
        target_cities = [city]

    for c in target_cities:
        if preset_format in ("markdown", "md"):
            exporter = MarkdownExporter(db)
            exporter.export_city_with_preset(c, preset, preset_config)
        else:
            exporter = CsvExporter(db)
            exporter.export_city_with_preset(c, preset, preset_config)

    print_status("Экспорт пресета завершен!", "success")
    db.engine.dispose()

# ===== Команды управления миграциями =====

db_app = typer.Typer(help="Управление схемой базы данных (Alembic миграции)")
app.add_typer(db_app, name="db")


def _get_alembic_config():
    """Подготовить конфигурацию Alembic для CLI-команд."""
    from alembic.config import Config
    config = load_config()
    db_path = config.get("database", {}).get("path", "data/granite.db")

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    # Передаём путь к config.yaml для env.py
    os.environ["GRANITE_CONFIG"] = _config_path

    return alembic_cfg


@db_app.command("upgrade")
def db_upgrade(
    revision: str = typer.Argument("head", help="Целевая ревизия (head, base, или ID)")
):
    """Применить миграции до указанной ревизии."""
    try:
        alembic_cfg = _get_alembic_config()
        from alembic import command
        command.upgrade(alembic_cfg, revision)
        print_status(f"Миграция применена: {revision}", "success")
    except Exception as e:
        print_status(f"Ошибка миграции: {e}", "error")
        raise typer.Exit(1)


@db_app.command("downgrade")
def db_downgrade(
    revision: str = typer.Argument("-1", help="Целевая ревизия (-1 = на одну назад, base = удалить всё)")
):
    """Откатить миграции до указанной ревизии."""
    try:
        alembic_cfg = _get_alembic_config()
        from alembic import command

        # Подтверждение для отката более чем на одну версию или до base
        try:
            rev_num = int(revision)
        except ValueError:
            print_status(f"Ошибка: неверный формат revision: {revision}", "error")
            raise typer.Exit(1)

        if revision in ("base", "0") or (revision.startswith("-") and rev_num < -1):
            confirm = typer.confirm(f"Вы уверены, что хотите откатить до {revision}? Это может удалить данные.")
            if not confirm:
                raise typer.Exit(0)

        command.downgrade(alembic_cfg, revision)
        print_status(f"Откат выполнен: {revision}", "success")
    except typer.Exit:
        raise
    except Exception as e:
        print_status(f"Ошибка отката: {e}", "error")
        raise typer.Exit(1)


@db_app.command("history")
def db_history(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Показать детали каждой миграции"),
    rev_range: str = typer.Option(None, "--range", "-r", help="Диапазон (например: base..head, rev1..rev2)")
):
    """Показать историю миграций."""
    try:
        alembic_cfg = _get_alembic_config()
        from alembic import command
        command.history(alembic_cfg, verbose=verbose, rev_range=rev_range)
    except Exception as e:
        print_status(f"Ошибка: {e}", "error")
        raise typer.Exit(1)


@db_app.command("current")
def db_current():
    """Показать текущую версию схемы БД."""
    try:
        alembic_cfg = _get_alembic_config()
        from alembic import command
        command.current(alembic_cfg, verbose=True)
    except Exception as e:
        print_status(f"Ошибка: {e}", "error")
        raise typer.Exit(1)


@db_app.command("migrate")
def db_migrate(
    message: str = typer.Argument(..., help="Описание миграции (например: 'add phone column')")
):
    """Создать новую миграцию на основе изменений в ORM-моделях (autogenerate)."""
    try:
        alembic_cfg = _get_alembic_config()
        from alembic import command
        command.revision(alembic_cfg, message=message, autogenerate=True)
        print_status("Новая миграция создана в alembic/versions/", "success")
        print_status("Проверьте и при необходимости отредактируйте файл перед применением.", "info")
    except Exception as e:
        print_status(f"Ошибка создания миграции: {e}", "error")
        raise typer.Exit(1)


@db_app.command("stamp")
def db_stamp(
    revision: str = typer.Argument("head", help="Ревизия для маркировки (head, base, или ID)")
):
    """Пометить текущую версию БД без выполнения миграций (для существующих БД)."""
    try:
        alembic_cfg = _get_alembic_config()
        from alembic import command

        confirm = typer.confirm(f"Пометить БД как '{revision}' без выполнения миграций?")
        if not confirm:
            raise typer.Exit(0)

        command.stamp(alembic_cfg, revision)
        print_status(f"БД помечена как ревизия: {revision}", "success")
    except typer.Exit:
        raise
    except Exception as e:
        print_status(f"Ошибка: {e}", "error")
        raise typer.Exit(1)


@db_app.command("check")
def db_check():
    """Проверить, есть ли незаписанные изменения в ORM-моделях."""
    try:
        alembic_cfg = _get_alembic_config()
        from alembic import command
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(alembic_cfg)

        # Сравниваем текущую схему БД с ORM-моделями
        from granite.database import Base
        import granite.database  # noqa: F401

        from alembic.autogenerate import compare_metadata
        from alembic.migration import MigrationContext
        from sqlalchemy import create_engine

        config = load_config()
        db_path = config.get("database", {}).get("path", "data/granite.db")
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

        try:
            with engine.connect() as conn:
                migration_context = MigrationContext.configure(conn)
                diff = compare_metadata(migration_context, Base.metadata)

            if not diff:
                print_status("Схема БД совпадает с ORM-моделями — миграции не нужны.", "success")
            else:
                print_status(f"Обнаружено {len(diff)} различий между ORM и БД:", "warning")
                for item in diff:
                    print(f"  • {item}")
                print_status("Запустите 'python cli.py db migrate \"описание\"' для создания миграции.", "info")
        finally:
            engine.dispose()

    except Exception as e:
        print_status(f"Ошибка проверки: {e}", "error")
        raise typer.Exit(1)


@app.command()
def precheck(
    city: str = typer.Argument(None, help="Город для проверки, или 'all' (по умолчанию)"),
    force: bool = typer.Option(False, "--force", help="Перепроверить даже закэшированные города"),
):
    """Предзаполнить кэш категорий jsprav для всех городов.

    Первый запуск занимает 18-28 минут (1098 городов × 2-3 запроса).
    Повторные запуски — мгновенно (из кэша).
    """
    config = load_config()
    setup_logging(config)

    from granite.pipeline.region_resolver import RegionResolver
    from granite.category_finder import discover_categories, _load_cache, _save_cache
    resolver = RegionResolver(config)

    if city and city.lower() != "all":
        cities = [city]
    else:
        cities = resolver.get_all_cities()
        print_status(f"Всего городов: {len(cities)}", "info")

    if force:
        cache = _load_cache()
        removed = 0
        for c in cities:
            if cache.get("jsprav", {}).pop(c, None) is not None:
                removed += 1
        if removed:
            _save_cache(cache)
            print_status(f"--force: очищено {removed} записей из кэша", "info")

    cache = discover_categories(cities, config)

    positive = sum(1 for v in cache.get("jsprav", {}).values() if v)
    negative = sum(1 for v in cache.get("jsprav", {}).values() if v == [])
    print_status(f"Результат: {positive} с категорией, {negative} без категории, всего {positive + negative}", "success")


@app.command()
def api(
    port: int = typer.Option(8000, "--port", "-p", help="Порт API сервера"),
    reload: bool = typer.Option(False, "--reload", help="Hot reload для разработки"),
):
    """Запустить CRM API сервер (FastAPI + uvicorn)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    import uvicorn
    uvicorn.run(
        "granite.api.app:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
    )


@app.command()
def seed_cities():
    """Заполнить справочник городов из regions.yaml."""
    config = load_config()
    setup_logging(config)
    db = Database(config_path=_config_path)
    from granite.pipeline.region_resolver import seed_cities_table
    count = seed_cities_table(db)
    if count > 0:
        print_status(f"Заполнено {count} городов в справочник", "success")
    else:
        print_status("Справочник уже заполнен", "info")
    db.engine.dispose()


@app.command()
def unmatched():
    """Показать неразрешённые города (не из regions.yaml)."""
    config = load_config()
    setup_logging(config)
    db = Database(config_path=_config_path)
    from granite.database import UnmatchedCityRow
    with db.session_scope() as session:
        results = session.query(UnmatchedCityRow).filter_by(resolved=False).all()
    if not results:
        print_status("Нет неразрешённых городов", "success")
    else:
        print_status(f"Неразрешённых городов: {len(results)}", "warning")
        for r in results:
            print(f"  [{r.detected_from}] {r.name} — {(r.context or '')[:60]}")
    db.engine.dispose()


@app.command()
def cities_status():
    """Показать статус обработки городов."""
    from collections import defaultdict
    config = load_config()
    setup_logging(config)
    db = Database(config_path=_config_path)
    from granite.database import CityRefRow, RawCompanyRow, CompanyRow, EnrichedCompanyRow
    from sqlalchemy import func

    with db.session_scope() as session:
        cities = session.query(CityRefRow).all()
        if not cities:
            print_status("Справочник городов пуст. Запустите seed-cities.", "warning")
            db.engine.dispose()
            return

        # GROUP BY — 3 запроса вместо 3×N
        raw_counts = dict(
            session.query(RawCompanyRow.city, func.count(RawCompanyRow.id))
            .group_by(RawCompanyRow.city).all()
        )
        comp_counts = dict(
            session.query(CompanyRow.city, func.count(CompanyRow.id))
            .group_by(CompanyRow.city).all()
        )
        enriched_counts = dict(
            session.query(EnrichedCompanyRow.city, func.count(EnrichedCompanyRow.id))
            .group_by(EnrichedCompanyRow.city).all()
        )

        results = []
        for c in cities:
            results.append({
                "city": c.name,
                "region": c.region,
                "raw": raw_counts.get(c.name, 0),
                "companies": comp_counts.get(c.name, 0),
                "enriched": enriched_counts.get(c.name, 0),
                "is_populated": c.is_populated,
            })

    by_region = defaultdict(list)
    for r in results:
        by_region[r["region"]].append(r)

    for region in sorted(by_region):
        print(f"\n{region}:")
        for r in sorted(by_region[region], key=lambda x: x["city"]):
            enriched_mark = "+" if r["enriched"] > 0 else " "
            pop_mark = "*" if r["is_populated"] else " "
            print(f"  {enriched_mark}{pop_mark} {r['city']}: raw={r['raw']} "
                  f"comp={r['companies']} enriched={r['enriched']}")

    print(f"\nВсего городов: {len(results)}")
    print("  + = enriched  * = populated (переназначенный)")
    db.engine.dispose()


@app.command()
def scan_networks():
    """А-6: Глобальный поиск агрегаторских сетей (3+ города) и их маркировка."""
    config = load_config()
    setup_logging(config)
    db = Database(config_path=_config_path)
    
    modified = detect_and_mark_aggregators(db)
    if modified > 0:
        print_status(f"Успешно: помечено {modified} записей как сети/агрегаторы", "success")
    else:
        print_status("Сетей или новых агрегаторов не обнаружено", "info")
    db.engine.dispose()


if __name__ == "__main__":
    app()
