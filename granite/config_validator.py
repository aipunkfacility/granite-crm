# granite/config_validator.py
"""Валидация конфигурации config.yaml.

Вынесен из cli.py, чтобы избежать циклического импорта database.py ↔ cli.py.
Database.__init__() использует _validate_config(), но не должен зависеть от cli.py.

Список городов перенесён в data/regions.yaml — секция cities больше не требуется.
"""

from granite.pipeline.status import print_status


def validate_config(config: dict) -> bool:
    """Проверяет критические поля конфигурации при загрузке.

    Валидирует структуру и типы ключевых секций, чтобы ошибки проявились
    немедленно при запуске, а не через 30 минут работы пайплайна.
    """
    if not isinstance(config, dict):
        print_status("Конфиг должен быть словарём (mapping) на верхнем уровне", "error")
        return False

    errors = []

    # scoring.weights — если есть, все значения должны быть числами
    weights = config.get("scoring", {}).get("weights", {})
    if isinstance(weights, dict):
        for key, val in weights.items():
            if not isinstance(val, (int, float)):
                errors.append(f"scoring.weights.{key} = {val!r} — ожидается число")

    # scoring.levels — если есть, пороги должны быть числами
    levels = config.get("scoring", {}).get("levels", {})
    if isinstance(levels, dict):
        for key, val in levels.items():
            if not isinstance(val, (int, float)):
                errors.append(f"scoring.levels.{key} = {val!r} — ожидается число")

    # database.path — если есть, должна быть строкой
    db_cfg = config.get("database", {})
    if isinstance(db_cfg, dict):
        db_path = db_cfg.get("path")
        if db_path is not None and not isinstance(db_path, str):
            errors.append(f"database.path = {db_path!r} — ожидается строка")

    # scraping.max_threads — если есть, должно быть целым числом > 0
    scrape_cfg = config.get("scraping", {})
    if isinstance(scrape_cfg, dict):
        max_threads = scrape_cfg.get("max_threads")
        if max_threads is not None:
            if not isinstance(max_threads, int) or max_threads < 1:
                errors.append(f"scraping.max_threads = {max_threads!r} — ожидается целое число > 0")

    # email — валидация критических полей
    email_cfg = config.get("email", {})
    if isinstance(email_cfg, dict):
        _email_int_fields = {
            "send_delay_min": (0, 600),
            "send_delay_max": (0, 600),
            "daily_limit": (1, 10000),
            "max_sends_per_run": (1, 10000),
            "session_gap_hrs": (0, 72),
            "bounce_threshold": (1, 100),
            "bounce_window_hrs": (1, 168),
            "followup_delay_days": (0, 90),
            "smtp_retry_attempts": (1, 10),
            "smtp_retry_backoff_min": (1, 60),
            "smtp_retry_backoff_max": (1, 300),
        }
        for field, (min_val, max_val) in _email_int_fields.items():
            val = email_cfg.get(field)
            if val is not None:
                if not isinstance(val, (int, float)):
                    errors.append(f"email.{field} = {val!r} — ожидается число")
                elif not (min_val <= val <= max_val):
                    errors.append(f"email.{field} = {val} — вне диапазона [{min_val}, {max_val}]")

        # send_delay_min <= send_delay_max
        d_min = email_cfg.get("send_delay_min")
        d_max = email_cfg.get("send_delay_max")
        if d_min is not None and d_max is not None and d_min > d_max:
            errors.append(f"email.send_delay_min ({d_min}) > send_delay_max ({d_max})")

        # smtp_retry_backoff_min <= smtp_retry_backoff_max
        b_min = email_cfg.get("smtp_retry_backoff_min")
        b_max = email_cfg.get("smtp_retry_backoff_max")
        if b_min is not None and b_max is not None and b_min > b_max:
            errors.append(f"email.smtp_retry_backoff_min ({b_min}) > smtp_retry_backoff_max ({b_max})")

    for err in errors:
        print_status(f"  Config validation: {err}", "error")

    if errors:
        print_status(f"Найдено {len(errors)} ошибок в конфигурации", "error")
        return False
    return True
