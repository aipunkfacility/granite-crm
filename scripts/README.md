# scripts/ — Устаревшие и отладочные скрипты

Эта директория содержит legacy-скрипты, которые были заменены основным приложением
(модули `scrapers/`, `dedup/`, `enrichers/`, `pipeline/`). Скрипты оставлены для
исторической справки и отладки, но не используются в пайплайне.

## Статус

| Файл | Описание | Статус |
|------|----------|--------|
| `scrape_fast.py` | Первый скрепер jsprav.ru (UTF-16 BOM) | **Заменён** на `scrapers/jsprav.py` |
| `scrape_fast_utf8.py` | UTF-8 версия скрепера с мессенджерами | **Заменён** на модули `scrapers/` + `enrichers/` |
| `scrape_city.py` | Полный Playwright-скрепер (все источники) | **Заменён** на `pipeline/manager.py` |
| `firecrawl_granite.py` | Standalone Firecrawl-скрепер | **Заменён** на `scrapers/firecrawl.py` |
| `tg_phone_finder.py` | Поиск TG по телефону (Telethon/Pyrogram) | **Заменён** на `enrichers/tg_finder.py` |
| `test_dgis.py` | Отладка: тест DGIS-скрепера | Отладочный, не используется |
| `test_scrapers.py` | Отладка: тест всех скреперов | Отладочный, не используется |
| `debug_dgis_selectors.py` | Отладка: исследование DGIS-селекторов | Отладочный, не используется |
| `debug_dgis_captcha.py` | Отладка: обнаружение капчи DGIS | Отладочный, не используется |
| `pyproject.toml` / `uv.lock` | Отдельный uv-проект для скриптов | Legacy-зависимости |

## Примечание

Эти скрипты не поддерживаются и могут содержать устаревшие зависимости.
Для всех операций используйте CLI: `python cli.py run <город>`.
