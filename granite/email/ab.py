"""A/B-тестирование email-тем — детерминированное распределение.

Задача 3 (FIX-P1): Логика A/B распределения вынесена из campaigns.py
в отдельный модуль, чтобы:
- переиспользовать в follow-up (задача 11, этап 3)
- тестировать напрямую без запуска SSE
- иметь единый источник истины для A/B логики

Детерминированное распределение: MD5(company_id) % 2 → "A" или "B".
Один и тот же company_id ВСЕГДА получает один и тот же вариант,
что исключает перекосы при перезапуске кампании.
"""
import hashlib


__all__ = ["determine_ab_variant"]


def determine_ab_variant(
    company_id: int,
    subject_a: str,
    subject_b: str | None = None,
) -> tuple[str, str]:
    """Определить A/B-вариант темы письма для компании.

    Args:
        company_id: ID компании (ключ детерминированности).
        subject_a: Тема варианта A.
        subject_b: Тема варианта B (если None → только A).

    Returns:
        Кортеж (variant, subject):
        - variant: "A" или "B"
        - subject: выбранная тема письма
    """
    if not subject_b:
        return "A", subject_a

    hash_val = int(hashlib.md5(str(company_id).encode()).hexdigest(), 16)
    variant = "A" if hash_val % 2 == 0 else "B"
    subject = subject_a if variant == "A" else subject_b
    return variant, subject
