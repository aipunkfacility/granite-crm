# dedup/merger.py
from granite.utils import pick_best_value, extract_street, normalize_phone, sanitize_filename, is_seo_title, is_non_local_phone, is_aggregator_name
from loguru import logger
import os

# FIX: Лимиты контактов при слиянии кластеров.
# Мастерская в нише редко имеет >4 email и >6 телефонов.
# Превышение = признак ложного слияния разных компаний.
MAX_MERGE_EMAILS = 4
MAX_MERGE_PHONES = 6

# FIX: Свободные email-провайдеры — приоритет ниже, чем email на домене компании
_FREE_EMAIL_DOMAINS = frozenset({
    "mail.ru", "inbox.ru", "bk.ru", "list.ru", "yandex.ru", "ya.ru",
    "gmail.com", "googlemail.com", "hotmail.com", "outlook.com", "live.com",
    "rambler.ru", "yahoo.com", "protonmail.com", "zoho.com", "mail.com",
})


def _label(index: int) -> str:
    """A, B, ..., Z, AA, AB, ..."""
    result = ""
    while True:
        result = chr(ord("A") + index % 26) + result
        index = index // 26 - 1
        if index < 0:
            break
    return result


def merge_cluster(cluster_records: list[dict]) -> dict:
    """Слияние группы записей в одну Company.

    Правила:
    - name_best: самое длинное название
    - phones: объединение уникальных (FIX: с лимитом MAX_MERGE_PHONES)
    - address: самое длинное значение
    - website: самое длинное значение
    - emails: объединение уникальных (FIX: с лимитом MAX_MERGE_EMAILS, с приоритетом company-domain)
    - merged_from: список id исходных записей

    Args:
        cluster_records: список dict с полями RawCompany (из БД)
    """
    if not cluster_records:
        return {}

    # Объединяем messengers из всех raw-записей
    merged_messengers: dict = {}
    for r in cluster_records:
        messengers = r.get("messengers")
        if isinstance(messengers, dict):
            for k, v in messengers.items():
                if v and k not in merged_messengers:
                    merged_messengers[k] = v

    # Объединяем все телефоны с нормализацией и дедупликацией
    all_phones: list[str] = []
    seen_phones: set[str] = set()
    for r in cluster_records:
        for p in r.get("phones", []):
            norm = normalize_phone(p)
            if norm and norm not in seen_phones:
                seen_phones.add(norm)
                all_phones.append(norm)

    # Объединяем email с дедупликацией
    all_emails: list[str] = []
    seen_emails: set[str] = set()
    for r in cluster_records:
        for e in r.get("emails", []):
            if e and isinstance(e, str) and e.strip():
                e_clean = e.strip().lower()
                if e_clean not in seen_emails:
                    seen_emails.add(e_clean)
                    all_emails.append(e_clean)

    # FIX: Сортируем email по приоритету:
    # 1) Email на домене компании (если website известен)
    # 2) На прочих доменах
    # 3) На free-провайдерах
    # Определяем домен компании из website (берём из первой записи с website)
    company_domain = None
    for r in cluster_records:
        ws = r.get("website", "") or ""
        if ws:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(ws if "://" in ws else f"https://{ws}")
                dom = parsed.netloc.lower()
                if dom.startswith("www."):
                    dom = dom[4:]
                if dom and "." in dom:
                    company_domain = dom
                    break
            except Exception:
                continue

    if company_domain:
        def _email_priority(em: str) -> int:
            em_dom = em.rsplit("@", 1)[-1].lower()
            if em_dom == company_domain or em_dom.endswith("." + company_domain):
                return 0  # свой домен — высший приоритет
            if em_dom in _FREE_EMAIL_DOMAINS:
                return 2  # free-провайдер — низкий приоритет
            return 1
        all_emails.sort(key=_email_priority)

    # FIX: Применяем лимиты
    phones_before_limit = len(all_phones)
    emails_before_limit = len(all_emails)
    if len(all_phones) > MAX_MERGE_PHONES:
        logger.warning(
            f"merge_cluster: обрезка телефонов {len(all_phones)} → {MAX_MERGE_PHONES} "
            f"(вероятно ложное слияние)"
        )
        all_phones = all_phones[:MAX_MERGE_PHONES]
    if len(all_emails) > MAX_MERGE_EMAILS:
        logger.warning(
            f"merge_cluster: обрезка email {len(all_emails)} → {MAX_MERGE_EMAILS} "
            f"(вероятно ложное слияние)"
        )
        all_emails = all_emails[:MAX_MERGE_EMAILS]

    # Собираем уникальные источники из всех raw-записей кластера
    sources_set: set[str] = set()
    for r in cluster_records:
        src = r.get("source")
        if src and isinstance(src, str) and src.strip():
            sources_set.add(src.strip())

    merged = {
        "merged_from": [r.get("id") for r in cluster_records if r.get("id") is not None],
        "sources": sorted(sources_set),
        # FIX 2.1: SEO-название не должно побеждать реальное имя.
        # pick_best_value берёт самое длинное → SEO-титлы (78+ символов) всегда выигрывают.
        # Новая логика: если есть не-SEO варианты — берём самое длинное из них.
        # Если все SEO — берём самое короткое (ближе к реальному названию).
        "name_best": (
            # 1. Приоритет: не-SEO и не-агрегаторское имя (самое длинное)
            max(
                (n for n in (r.get("name", "") for r in cluster_records) 
                 if n and not is_seo_title(n) and not is_aggregator_name(n)),
                key=len, default=None
            )
            # 2. Если все SEO — берём не-агрегаторское самое короткое (ближе к сути)
            or min(
                (n for n in (r.get("name", "") for r in cluster_records) 
                 if n and not is_aggregator_name(n)),
                key=len, default=None
            )
            # 3. Fallback: самое короткое из всего что есть
            or min(
                (n for n in (r.get("name", "") for r in cluster_records) if n),
                key=len, default=""
            )
        ),
        "phones": all_phones,
        "address": pick_best_value(
            *(r.get("address_raw", "") for r in cluster_records)
        ),
        "website": pick_best_value(
            *(r.get("website", "") or "" for r in cluster_records)
        ),
        "emails": all_emails,
        "messengers": merged_messengers,
        "city": cluster_records[0].get("city", ""),
        "needs_review": any(r.get("needs_review", False) for r in cluster_records),
        "review_reason": " ".join(sorted(set(r.get("review_reason", "") for r in cluster_records if r.get("review_reason")))).strip(),
    }

    # Очищаем пустые website
    if not merged["website"]:
        merged["website"] = None

    # FIX: Если контактов было обрезано — это признак ложного слияния.
    # Помечаем needs_review даже если названия похожи.
    if phones_before_limit > MAX_MERGE_PHONES or emails_before_limit > MAX_MERGE_EMAILS:
        merged["needs_review"] = True
        if merged["review_reason"]:
            merged["review_reason"] += " contacts_over_limit"
        else:
            merged["review_reason"] = "contacts_over_limit"

    # Проверка: одинаковые названия, но разные адреса → конфликт
    streets = [extract_street(r.get("address_raw", "")) for r in cluster_records]
    unique_streets = {s for s in streets if s}

    if len(unique_streets) > 1:
        # Проверяем, действительно ли названия похожи — если нет, это разные компании
        names_raw = [r.get("name", "") for r in cluster_records]
        unique_names = list({n.strip().lower() for n in names_raw if n and n.strip()})

        def _jaccard_words(a: str, b: str) -> float:
            sa, sb = set(a.split()), set(b.split())
            if not sa or not sb:
                return 0.0
            return len(sa & sb) / len(sa | sb)

        names_similar = True
        if unique_names:
            for i in range(len(unique_names)):
                for j in range(i + 1, len(unique_names)):
                    if _jaccard_words(unique_names[i], unique_names[j]) <= 0.5:
                        names_similar = False
                        break
                if not names_similar:
                    break

        # Если названия совсем разные (Jaccard < 0.3) и адреса разные —
        # это точно разные компании, объединённые ошибочно по телефону
        if len(unique_names) > 1 and not names_similar:
            merged["needs_review"] = True
            if merged["review_reason"]:
                merged["review_reason"] += " different_names_different_addresses"
            else:
                merged["review_reason"] = "different_names_different_addresses"
        elif len(unique_names) <= 2 and names_similar:
            # Названия похожие, но адреса разные — помечаем для ручной проверки
            merged["needs_review"] = True
            if merged["review_reason"]:
                merged["review_reason"] += " same_name_diff_address"
            else:
                merged["review_reason"] = "same_name_diff_address"

    # Проверка: разные города в кластере → конфликт
    cities = [r.get("city", "") for r in cluster_records if r.get("city")]
    if len(set(cities)) > 1:
        merged["needs_review"] = True
        if merged.get("review_reason"):
            merged["review_reason"] = (merged["review_reason"] + " different_cities").strip()
        else:
            merged["review_reason"] = "different_cities"

    # A-5: Если все телефоны не-локальные для города кластера → подозрение на агрегатор
    # Москovsky/piter DEF для провинциального города = колл-центр, не мастерская
    cluster_city = merged.get("city", "")
    if cluster_city and all_phones:
        non_local_count = sum(1 for p in all_phones if is_non_local_phone(p, cluster_city))
        if non_local_count == len(all_phones) and len(all_phones) > 0:
            merged["needs_review"] = True
            reason = "all_non_local_phones"
            if merged.get("review_reason"):
                merged["review_reason"] = (merged["review_reason"] + f" {reason}").strip()
            else:
                merged["review_reason"] = reason
            logger.debug(
                f"merge_cluster: A-5 помечено needs_review — "
                f"{len(all_phones)} не-локальных телефонов для {cluster_city}"
            )

    return merged


def generate_conflicts_md(
    conflicts: list[dict], city: str, output_dir: str = "data/conflicts"
):
    """Генерация conflicts.md для Human-in-the-loop.

    Args:
        conflicts: список dict с полями:
            - "cluster_id": int
            - "records": list[dict] — исходные записи из кластера
            - "reason": str
        city: название города
        output_dir: путь для сохранения
    """
    if not conflicts:
        return

    os.makedirs(output_dir, exist_ok=True)
    safe_city = sanitize_filename(city)
    filepath = os.path.join(output_dir, f"{safe_city}_conflicts.md")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Конфликты дедупликации — {city}\n\n")
        f.write(f"**Найдено конфликтов:** {len(conflicts)}\n\n")
        f.write("Для каждого конфликта отметьте правильный вариант `[x]`:\n\n")
        f.write("---\n\n")

        for i, conflict in enumerate(conflicts, 1):
            f.write(f"## {i}. Конфликт #{conflict.get('cluster_id', '?')}\n\n")
            f.write(f"**Причина:** {conflict.get('reason', '?')}\n\n")

            records = conflict["records"]
            for j, record in enumerate(records):
                letter = _label(j)
                f.write(f"- [ ] **Вариант {letter}:** {record.get('name', 'N/A')}\n")
                f.write(f"  Адрес: {record.get('address_raw', 'N/A')}\n")
                f.write(f"  Телефон: {', '.join(record.get('phones', []))}\n")
                f.write(f"  Сайт: {record.get('website', 'N/A')}\n")
                f.write(f"  Источник: {record.get('source', 'N/A')}\n")
                f.write(f"  ID: {record.get('id', 'N/A')}\n\n")

            f.write(f"- [ ] **Разные компании** (не объединять)\n\n")
            f.write("---\n\n")

    logger.info(f"Conflicts сохранены: {filepath} ({len(conflicts)} конфликтов)")
