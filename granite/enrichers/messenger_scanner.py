# enrichers/messenger_scanner.py
import re
from urllib.parse import urljoin, urlparse
from loguru import logger
from granite.utils import fetch_page, adaptive_delay, is_safe_url


class MessengerScanner:
    """Сканирует сайт на наличие ссылок на мессенджеры и соцсети."""

    def __init__(self, config: dict):
        pass

    def scan_website(self, base_url: str) -> dict:
        """Сканирует сайт: сначала главная, затем найденные страницы."""
        found_messengers: dict = {}

        if not base_url:
            return found_messengers

        base_url_clean = base_url.rstrip("/")

        if not is_safe_url(base_url_clean):
            return found_messengers

        html = None
        contacts_url = None

        # 1. Сканируем главную страницу
        try:
            html = fetch_page(base_url_clean + "/", timeout=10)
            if html:
                self._extract_social_links(html, found_messengers)
        except Exception as e:
            logger.debug(f"MessengerScanner scan_website main page error: {e}")

        # Если уже нашли telegram — скорее всего этого достаточно
        if "telegram" in found_messengers:
            return found_messengers

        # 2. Ищем ссылки на странице контактов с главной
        try:
            adaptive_delay()
            contacts_url = self._find_contacts_link(base_url_clean, html)
            if contacts_url:
                if not is_safe_url(contacts_url):
                    contacts_url = None
                    chtml = None
                else:
                    chtml = fetch_page(contacts_url, timeout=10)
                if chtml:
                    self._extract_social_links(chtml, found_messengers)
                    # На странице контактов ищем ссылки на другие страницы
                    extra_links = self._find_relevant_links(chtml, base_url_clean)
                    for link in extra_links:
                        if link == contacts_url:
                            continue
                        if (
                            "telegram" in found_messengers
                            and "whatsapp" in found_messengers
                        ):
                            break
                        if not is_safe_url(link):
                            continue
                        try:
                            adaptive_delay()
                            ehtml = fetch_page(link, timeout=10)
                            if ehtml:
                                self._extract_social_links(ehtml, found_messengers)
                        except Exception as e:
                            logger.debug(f"MessengerScanner extra page error: {e}")
                            continue
        except Exception as e:
            logger.debug(f"MessengerScanner contacts page error: {e}")

        return found_messengers

    def _find_contacts_link(self, base_url: str, html: str) -> str | None:
        """Ищет ссылку на страницу контактов в HTML главной страницы."""
        if not html:
            return None

        # Ищем ссылки по тексту и URL
        contact_patterns = [
            r'href=["\']([^"\']+)["\'][^>]*>[^<]*(?:контакт|связ|телефон|обратн)[^<]*</a>',
            r'href=["\']([^"\']*(?:contact|kontakt|kontakty|kontaktyi|about|o-nas|o_kompanii)[^"\']*)["\']',
        ]

        soup_pattern = re.compile(
            r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )

        found_links = []
        seen_hrefs = set()

        for match in soup_pattern.finditer(html):
            href = match.group(1)
            text = re.sub(r"<[^>]+>", "", match.group(2)).strip().lower()

            if href.startswith(("#", "javascript:", "tel:", "mailto:")):
                continue
            if href in seen_hrefs:
                continue

            # По тексту ссылки
            if any(
                kw in text
                for kw in ["контакт", "связ", "телефон", "обратн", "написать"]
            ):
                full_url = urljoin(base_url + "/", href)
                found_links.append(full_url)
                seen_hrefs.add(href)
                continue

            # По URL
            href_lower = href.lower()
            if any(
                p in href_lower for p in ["contact", "kontakt", "kontakty", "kontaktyi"]
            ):
                full_url = urljoin(base_url + "/", href)
                found_links.append(full_url)
                seen_hrefs.add(href)

        if found_links:
            return found_links[0]
        return None

    def _find_relevant_links(self, html: str, base_url: str) -> list[str]:
        """Находит ссылки на полезные страницы (о нас, производство, каталог)."""
        links = []
        seen = set()

        link_pattern = re.compile(r'<a\s[^>]*href=["\']([^"\']+)["\']', re.IGNORECASE)

        for match in link_pattern.finditer(html):
            href = match.group(1)
            if href.startswith(("#", "javascript:", "tel:", "mailto:")):
                continue
            href_lower = href.lower()
            if href_lower in seen:
                continue

            # Только ссылки на тот же домен
            full_url = urljoin(base_url + "/", href)
            if urlparse(full_url).netloc != urlparse(base_url).netloc:
                continue

            # Интересующие страницы
            if any(
                kw in href_lower
                for kw in [
                    "about",
                    "o-nas",
                    "o_kompanii",
                    "production",
                    "proizvodstvo",
                    "catalog",
                    "katalog",
                    "uslugi",
                    "services",
                ]
            ):
                links.append(full_url)
                seen.add(href_lower)

        return links[:3]  # не более 3 доп. страниц

    def _extract_social_links(self, html: str, result: dict):
        """Парсинг ссылок из HTML и запись в result dict."""
        if not html:
            return

        # Telegram: t.me, telegram.me
        for m in re.finditer(
            r'href=["\'](https?://(?:t\.me|telegram\.me)/([^"\'\s]+))["\']', html
        ):
            link = m.group(1).rstrip("/")
            if not any(
                kw in link.lower() for kw in ["share", "joinchat"]
            ):  # пропускаем кнопки "поделиться"
                if "telegram" not in result:
                    result["telegram"] = link

        # WhatsApp: wa.me, api.whatsapp.com
        for m in re.finditer(
            r'href=["\'](https?://(?:wa\.me|api\.whatsapp\.com/send\?phone=[^"\'\s]+))["\']',
            html,
        ):
            if "whatsapp" not in result:
                result["whatsapp"] = m.group(1)

        # VK
        for m in re.finditer(
            r'href=["\'](https?://(?:www\.)?vk\.com/([^"\'\s]+))["\']', html
        ):
            if "vk" not in result:
                result["vk"] = m.group(1)
