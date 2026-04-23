# dedup/site_matcher.py
from granite.utils import extract_domain, extract_base_domain


# Domains excluded from base-domain clustering to prevent over-merging
_EXCLUDED_FROM_BASE_CLUSTERING = frozenset({
    "danila-master.ru",
})


def cluster_by_site(companies: list[dict]) -> list[list[int]]:
    """Группировка по домену сайта.

    Записи с одинаковым доменом → один кластер.
    C3: Also clusters by base domain (SLD+TLD) to catch subdomain networks
    (e.g. *.danila-master.ru), excluding domains in _EXCLUDED_FROM_BASE_CLUSTERING.

    Args:
        companies: список dict с полями {"id": int, "website": str|None}
    """
    domain_to_ids: dict[str, list[int]] = {}

    for company in companies:
        company_id = company.get("id")
        if company_id is None:
            continue
        domain = extract_domain(company.get("website"))
        if domain:
            if domain not in domain_to_ids:
                domain_to_ids[domain] = []
            domain_to_ids[domain].append(company_id)

    clusters = [ids for ids in domain_to_ids.values() if len(ids) > 1]

    # C3: Base domain clustering (subdomain networks)
    existing_cluster_sets = [set(c) for c in clusters]

    base_domain_to_ids: dict[str, list[int]] = {}
    for company in companies:
        company_id = company.get("id")
        if company_id is None:
            continue
        website = company.get("website")
        base = extract_base_domain(website)
        if base and base not in _EXCLUDED_FROM_BASE_CLUSTERING:
            if base not in base_domain_to_ids:
                base_domain_to_ids[base] = []
            base_domain_to_ids[base].append(company_id)

    for base_domain, ids in base_domain_to_ids.items():
        if len(ids) < 2:
            continue
        base_set = set(ids)
        # Skip if this base-domain cluster is a subset of an existing domain cluster
        if any(base_set == existing for existing in existing_cluster_sets):
            continue
        clusters.append(ids)

    return clusters
