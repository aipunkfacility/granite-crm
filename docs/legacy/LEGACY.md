# Legacy-файлы (корень проекта)

Эти файлы расположены в корне репозитория и больше не используются в основном пайплайне.
Они сохранены для исторической справки. Не запускайте их напрямую — используйте CLI:
`python cli.py run <город>`.

## Статус

| Файл | Описание | Статус |
|------|----------|--------|
| `analyze_networks.py` | CSV-based обнаружение сетей, версия 1 | **Заменён** на `enrichers/network_detector.py` |
| `analyze_networks_v2.py` | Добавлена автоопределение кодировки CSV | **Заменён** на `enrichers/network_detector.py` |
| `analyze_networks_v3.py` | Ручной CSV-парсер (без pandas) | **Заменён** на `enrichers/network_detector.py` |
| `messenger_search.py` | Standalone-сканер мессенджеров | **Заменён** на `enrichers/messenger_scanner.py` |
| `run.bat` | Windows-лаунчер для `cli.py` | Актуален, но не критичен |

## Примечание

- Все три версии `analyze_networks*.py` читают CSV-файлы из `data/export/` и ищут компании,
  появляющиеся в нескольких городах (признак сети филиалов).
  Теперь это реализовано через ORM в `enrichers/network_detector.py` (по домену и телефону).

- `messenger_search.py` — автономный скрипт, который сканирует один сайт на наличие
  ссылок на Telegram, WhatsApp и VK. Заменён классом `MessengerScanner` в
  `enrichers/messenger_scanner.py`, который интегрирован в пайплайн обогащения.
