# enrichers/classifier.py

import re
from granite.utils import extract_domain, is_non_local_phone


class Classifier:
    """Оценка (скоринг) компаний по конфигурации config.yaml.
    Распределяет по сегментам (A, B, C, D, spam).
    """

    def __init__(self, config: dict):
        self.config = config
        self.rules = config.get("scoring", {})
        self.weights = self.rules.get("weights", {})
        self.thresholds = self.rules.get("levels", {})

        # AUDIT #17: Штрафы за иностранные TLD перенесены из hardcoded в config.
        # Формат: список {"tld": ".com", "penalty": -5}.
        # Если не задано — используется fallback (hardcoded в __init__).
        self.tld_penalties = self.rules.get("tld_penalties", [])
        if not self.tld_penalties:
            # Fallback: обратная совместимость со старым поведением
            self.tld_penalties = [
                {"tld": ".kz", "penalty": -5},
                {"tld": ".by", "penalty": -5},
                {"tld": ".com", "penalty": -3},
                {"tld": ".net", "penalty": -3},
                {"tld": ".org", "penalty": -3},
                {"tld": ".biz", "penalty": -5},
            ]

        # AUDIT #8: Веса для tech_keywords из config.yaml.
        # Категории: equipment, production, portrait, site_constructor.
        # Если не задано — используются дефолтные значения.
        self.tech_weights = self.rules.get("tech_weights", {})
        if not self.tech_weights:
            self.tech_weights = {
                "production": 8,    # «Собственное производство»
                "equipment": 5,     # «ЧПУ», «лазерный станок»
                "portrait": 2,      # «Фото на памятник»
                "site_constructor": -3,  # ucoz/narod — признак кустарного сайта
            }

        # SEO-паттерн для штрафа за некачественное имя
        self._seo_name = re.compile(
            r"(?:купить|цен[аыуе]|недорог|заказать|от производитель|"
            r"с установк|на могил|доставк|скидк)",
            re.IGNORECASE,
        )

    def calculate_score(self, company: dict) -> int:
        """Подсчет CRM Score на основе обогащенных данных.

        Включает позитивные сигналы (+) и штрафы (-) за негативные.
        """
        score = 0

        # ── Позитивные сигналы ──

        # Сайт
        if company.get("website"):
            score += self.weights.get("has_website", 0)

            cms = company.get("cms", "unknown")
            if cms == "bitrix":
                score += self.weights.get("cms_bitrix", 0)
            elif cms in ["wordpress", "tilda", "flexbe"]:
                score += self.weights.get("cms_modern", 0)

            if company.get("has_marquiz"):
                score += self.weights.get("has_marquiz", 0)

        # Мессенджеры
        messengers = company.get("messengers", {})
        if messengers.get("telegram"):
            score += self.weights.get("has_telegram", 0)

            tg_trust = company.get("tg_trust") or {}
            try:
                score += int(tg_trust.get("trust_score", 0) * self.weights.get("tg_trust_multiplier", 0))
            except (TypeError, ValueError):
                pass

            # Штраф -10 для бота-автоответчика: даже с multiplier=3 бот получит
            # -2×3+15 = 9 pts (с штрафом: -1), что ниже живого WhatsApp (+10).
            if tg_trust.get("is_bot"):
                score -= 10

        if messengers.get("whatsapp"):
            score += self.weights.get("has_whatsapp", 0)

        # Несколько телефонов
        phones = company.get("phones", [])
        if len(phones) > 1:
            score += self.weights.get("multiple_phones", 0)

        # E1: Penalty for all non-local phones (aggregator indicator)
        city_val = company.get("city", "")
        if phones and city_val:
            non_local_count = sum(1 for p in phones if is_non_local_phone(p, city_val))
            if non_local_count == len(phones) and len(phones) > 0:
                score -= self.weights.get("all_non_local_phones_penalty", 5)

        # Наличие Email
        emails = company.get("emails", [])
        if len(emails) > 0:
            score += self.weights.get("has_email", 0)

        # Сеть филиалов
        if company.get("is_network"):
            score += self.weights.get("is_network", 0)

        # AUDIT #8: tech_keywords — баллы за обнаруженные категории
        tech_signals = company.get("tech_signals") or {}
        for category, has_signal in tech_signals.items():
            if has_signal and category in self.tech_weights:
                score += self.tech_weights[category]

        # Адрес — признак реальной мастерской (AUDIT #5 рекомендация)
        if company.get("address_raw"):
            score += self.weights.get("has_address", 0)

        # ── Штрафы за негативные сигналы ──

        # AUDIT #17: TLD-штрафы из config.yaml вместо hardcoded.
        # Применяется только один (первый совпавший) штраф за TLD.
        website = company.get("website", "")
        domain = extract_domain(website) if website else ""
        if domain:
            for rule in self.tld_penalties:
                tld = rule.get("tld", "")
                penalty = rule.get("penalty", 0)
                if tld and domain.endswith(tld):
                    score += penalty
                    break

        # AUDIT #24: Убран двойной штраф «нет сайта».
        # Ранее: не получая +5 за has_website И получая -5 за no_website = -10.
        # Теперь: отсутствие сайта уже наказано невыдачей +5, дополнительный штраф снят.

        # SEO-имя → скорее всего агрегатор, не реальная компания
        name = (company.get("name") or "").lower()
        if self._seo_name.search(name):
            score -= 15

        return max(0, score)

    def determine_segment(self, score: int) -> str:
        """Определение сегмента на основе Score."""
        if score == 0:
            return "spam"
        elif score >= self.thresholds.get("segment_A", 50):
            return "A"
        elif score >= self.thresholds.get("segment_B", 30):
            return "B"
        elif score >= self.thresholds.get("segment_C", 15):
            return "C"
        else:
            return "D"
