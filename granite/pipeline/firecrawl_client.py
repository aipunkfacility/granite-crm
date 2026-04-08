# pipeline/firecrawl_client.py
"""Клиент для firecrawl CLI: поиск и скрапинг сайтов через subprocess.

Вынесен из PipelineManager для изоляции subprocess-вызовов,
устранения дублирования JSON-парсинга и возможности мокирования в тестах.
"""

import re
import subprocess
import json
from loguru import logger
from granite.utils import extract_emails, is_safe_url, _sanitize_url_for_log

MIN_MARKDOWN_LENGTH = 50


class FirecrawlClient:
    """Обёртка над firecrawl CLI (search + scrape)."""

    def __init__(
        self, timeout: int = 60, search_limit: int = 3
    ):
        self.timeout = timeout
        self.search_limit = search_limit

    # ── JSON-парсинг stdout (устраняет дублирование между search и scrape) ──

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """Extract first valid JSON object from text."""
        decoder = json.JSONDecoder()
        for i, ch in enumerate(text):
            if ch == '{':
                try:
                    obj, end = decoder.raw_decode(text, i)
                    return obj
                except json.JSONDecodeError:
                    continue
        return None

    def _parse_json_output(self, stdout: str) -> dict | None:
        """Парсит stdout firecrawl CLI как JSON.

        Пробует:
        1. Распарсить весь stdout как JSON
        2. Найти первый {...} блок через балансировку скобок
        """
        stdout = stdout.strip()
        if not stdout:
            return None

        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return self._extract_json(stdout)

    # ── Поиск ──

    def search(self, query: str) -> dict | None:
        """Поиск через firecrawl search CLI.

        Returns:
            dict с ключом "data.web" — список результатов, или None.
        """
        try:
            result = subprocess.run(
                ["firecrawl", "search", query, "--limit", str(self.search_limit)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )
            if result.returncode != 0 and result.stderr:
                logger.warning(
                    f"Firecrawl search stderr (rc={result.returncode}): "
                    f"{result.stderr.strip()[:300]}"
                )
                return None

            stdout = result.stdout.strip()
            if not stdout:
                return None

            parsed = self._parse_json_output(stdout)
            if parsed is None:
                logger.debug(
                    f"Firecrawl search: не удалось распарсить stdout ({len(stdout)} символов)"
                )
            return parsed

        except subprocess.TimeoutExpired:
            logger.warning(f"Firecrawl search таймаут: {query[:60]}")
            return None
        except FileNotFoundError:
            logger.error("firecrawl CLI не найден — установите firecrawl-cli")
            return None
        except Exception as e:
            logger.debug(f"Firecrawl search ошибка: {e}")
            return None

    # ── Скрапинг ──

    def scrape(self, url: str) -> dict | None:
        """Скрапинг сайта через firecrawl scrape CLI.

        Returns:
            {"phones": [...], "emails": [...]} или None.
        """
        if url and not url.startswith(("http://", "https://")):
            logger.warning(f"Skipping invalid URL: {_sanitize_url_for_log(url)}")
            return None

        # SSRF protection: block internal/private URLs before subprocess
        if not is_safe_url(url):
            logger.warning(f"SSRF blocked (firecrawl scrape): {_sanitize_url_for_log(url)}")
            return None

        try:
            result = subprocess.run(
                ["firecrawl", "scrape", url, "--format", "markdown"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )
            if result.returncode != 0 and result.stderr:
                logger.warning(
                    f"Firecrawl scrape stderr (rc={result.returncode}): "
                    f"{result.stderr.strip()[:300]}"
                )
                return None

            stdout = result.stdout.strip()
            if not stdout:
                return None

            # Пробуем распарсить как JSON
            data = self._parse_json_output(stdout)

            if not data:
                # Если не JSON — это может быть чистый markdown
                if len(stdout) > MIN_MARKDOWN_LENGTH:
                    markdown = stdout
                else:
                    return None
            else:
                markdown = ""
                d = data.get("data", {})
                if isinstance(d, dict):
                    markdown = d.get("markdown", "") or d.get("html", "")
                elif isinstance(d, str):
                    markdown = d
                if not markdown:
                    return None

            phones = re.findall(
                r"(\+?7[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2})",
                markdown,
            )
            return {"phones": phones, "emails": extract_emails(markdown)}

        except subprocess.TimeoutExpired:
            logger.warning(f"Firecrawl scrape таймаут: {_sanitize_url_for_log(url, 80)}")
            return None
        except FileNotFoundError:
            logger.error("firecrawl CLI не найден — установите firecrawl-cli")
            return None
        except Exception as e:
            logger.debug(f"Firecrawl scrape ошибка: {e}")
            return None
