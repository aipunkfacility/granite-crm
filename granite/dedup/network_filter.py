# dedup/network_filter.py
from sqlalchemy import func, text
from loguru import logger
from granite.database import Database, CompanyRow, EnrichedCompanyRow
from granite.utils import extract_domain, extract_base_domain

# Домены, которые мы считаем 100% спам-агрегаторами (даже если они в 2 городах)
# Единый источник — granite/constants.py
from granite.constants import SPAM_DOMAINS as KNOW_SPAM_DOMAINS, NON_NETWORK_DOMAINS


def _is_ua_region(dom: str | None) -> bool:
    return bool(dom and (dom.endswith('.ua') or dom.endswith('.xn--j1amh')))

def detect_and_mark_aggregators(db: Database) -> int:
    """A-6: Глобальный сканер для обнаружения сетей и агрегаторов.
    
    Находит домены, представленные в 3+ городах, и помечает их:
    1. В 'companies': adds needs_review=True и reason.
    2. В 'enriched_companies': adds is_network=True.
    3. Если в KNOW_SPAM_DOMAINS: segment='spam', score=0.
    
    Returns:
        Количество измененных записей.
    """
    logger.info("A-6: Запуск кросс-городской проверки на сети и агрегаторы...")
    
    modified_total = 0
    
    with db.session_scope() as session:
        # 1. Собираем статистику по доменам среди всех компаний
        # SQL-запрос для эффективности (SQLite группировка по домену)
        # Мы не можем просто группировать по полю website, т.к. там полные URL.
        # Поэтому сначала выгружаем все пары (id, website, city) и считаем в Python.
        
        query = session.query(CompanyRow.id, CompanyRow.website, CompanyRow.city).filter(CompanyRow.website.isnot(None))
        records = query.all()
        
        domain_to_cities = {}
        id_to_domain = {}
        id_to_website: dict[int, str] = {}
        
        for cid, website, city in records:
            domain = extract_domain(website)
            if not domain:
                continue
            
            id_to_domain[cid] = domain
            id_to_website[cid] = website
            if domain not in domain_to_cities:
                domain_to_cities[domain] = set()
            domain_to_cities[domain].add(city.lower())
        
        # 2. Определяем список доменов-сетей (3+ города)
        network_domains = {
            d for d, cities in domain_to_cities.items()
            if len(cities) >= 3
            and d not in NON_NETWORK_DOMAINS
            and d not in KNOW_SPAM_DOMAINS
            and not _is_ua_region(d)
        }
        logger.info(f"Найдено {len(network_domains)} доменов-сетей (3+ города)")
        
        if not network_domains and not KNOW_SPAM_DOMAINS:
            return 0
            
        # 3. Обновляем записи в БД
        for cid, domain in id_to_domain.items():
            is_network = domain in network_domains
            is_spam = domain in KNOW_SPAM_DOMAINS or _is_ua_region(domain)

            # Проверяем base_domain для SPAM_DOMAINS (ловит *.moyaspravka.ru и т.п.)
            if not is_spam:
                website = id_to_website.get(cid)
                if website:
                    base = extract_base_domain(website)
                    if base and base in KNOW_SPAM_DOMAINS:
                        is_spam = True
            
            if is_network or is_spam:
                comp = session.query(CompanyRow).get(cid)
                if not comp:
                    continue
                    
                changed = False
                
                if is_network:
                    if not comp.needs_review:
                        comp.needs_review = True
                        changed = True
                    
                    reason = f"aggregator_network({len(domain_to_cities[domain])} cities)"
                    if reason not in comp.review_reason:
                        comp.review_reason = (comp.review_reason + " " + reason).strip()
                        changed = True
                
                if is_spam:
                    if not comp.needs_review:
                        comp.needs_review = True
                        changed = True
                    if "known_spam_aggregator" not in comp.review_reason:
                        comp.review_reason = (comp.review_reason + " known_spam_aggregator").strip()
                        changed = True
                
                # Обновляем Enriched если есть (1:1)
                enriched = session.query(EnrichedCompanyRow).get(cid)
                if enriched:
                    if is_network and not is_spam:
                        if not enriched.is_network:
                            enriched.is_network = True
                            changed = True
                    
                    if is_spam:
                        if enriched.segment != "spam":
                            enriched.segment = "spam"
                            enriched.crm_score = 0
                            changed = True
                        if enriched.is_network:
                            enriched.is_network = False
                            changed = True
                
                if changed:
                    modified_total += 1

    logger.info(f"A-6: Обработка завершена. Помечено {modified_total} записей.")

    # 4. Дополнительный проход: компании с email-доменами .ua / .укр → spam
    _mark_ua_email_companies(db)

    return modified_total


def _mark_ua_email_companies(db: Database) -> int:
    """Помечает как spam компании, чьи email-домены оканчиваются на .ua или .укр."""
    marked = 0
    with db.session_scope() as session:
        rows = session.query(CompanyRow.id, CompanyRow.emails).filter(
            CompanyRow.emails.isnot(None),
            CompanyRow.emails != "",
        ).all()
        for cid, emails_str in rows:
            if not emails_str:
                continue
            emails_list = emails_str if isinstance(emails_str, list) else [emails_str]
            has_ua = False
            for email in emails_list:
                if isinstance(email, str) and '@' in email:
                    domain = email.split('@', 1)[1].lower().strip()
                    if _is_ua_region(domain):
                        has_ua = True
                        break
            if not has_ua:
                continue
            comp = session.query(CompanyRow).get(cid)
            if not comp:
                continue
            if not comp.needs_review:
                comp.needs_review = True
            if "ua_email_spam" not in comp.review_reason:
                comp.review_reason = (comp.review_reason + " ua_email_spam").strip()
            enriched = session.query(EnrichedCompanyRow).get(cid)
            if enriched:
                if enriched.segment != "spam":
                    enriched.segment = "spam"
                    enriched.crm_score = 0
                if enriched.is_network:
                    enriched.is_network = False
            marked += 1
    if marked:
        logger.info(f"A-6 email: Помечено {marked} компаний с .ua/.укр email-доменами")
    return marked
