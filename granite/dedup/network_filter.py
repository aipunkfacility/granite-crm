# dedup/network_filter.py
from sqlalchemy import func, text
from loguru import logger
from granite.database import Database, CompanyRow, EnrichedCompanyRow
from granite.utils import extract_domain

# Домены, которые мы считаем 100% спам-агрегаторами (даже если они в 2 городах)
KNOW_SPAM_DOMAINS = frozenset({
    "uslugio.com", "zoon.ru", "jsprav.ru", "yell.ru", 
    "orgpage.ru", "spravka-inform.ru", "2gis.ru",
})

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
        
        for cid, website, city in records:
            domain = extract_domain(website)
            if not domain:
                continue
            
            id_to_domain[cid] = domain
            if domain not in domain_to_cities:
                domain_to_cities[domain] = set()
            domain_to_cities[domain].add(city.lower())
        
        # 2. Определяем список доменов-сетей (3+ города)
        network_domains = {d for d, cities in domain_to_cities.items() if len(cities) >= 3}
        logger.info(f"Найдено {len(network_domains)} доменов-сетей (3+ города)")
        
        if not network_domains:
            return 0
            
        # 3. Обновляем записи в БД
        # Для ускорения используем UPDATE ... WHERE website IN (...) или по ID
        # Но так как у нас есть еще и EnrichedCompanyRow, пройдемся циклом
        
        # Обновляем CompanyRow
        for cid, domain in id_to_domain.items():
            is_network = domain in network_domains
            is_spam = domain in KNOW_SPAM_DOMAINS
            
            if is_network or is_spam:
                comp = session.query(CompanyRow).get(cid)
                if not comp:
                    continue
                    
                changed = False
                if not comp.needs_review:
                    comp.needs_review = True
                    changed = True
                
                reason = f"aggregator_network({len(domain_to_cities[domain])} cities)" if is_network else "known_spam_aggregator"
                if reason not in comp.review_reason:
                    comp.review_reason = (comp.review_reason + " " + reason).strip()
                    changed = True
                
                # Обновляем Enriched если есть (1:1)
                enriched = session.query(EnrichedCompanyRow).get(cid)
                if enriched:
                    if not enriched.is_network:
                        enriched.is_network = True
                        changed = True
                    
                    if is_spam:
                        if enriched.segment != "spam":
                            enriched.segment = "spam"
                            enriched.crm_score = 0
                            changed = True
                
                if changed:
                    modified_total += 1

    logger.info(f"A-6: Обработка завершена. Помечено {modified_total} записей.")
    return modified_total
