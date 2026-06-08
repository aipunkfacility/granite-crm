"""
Analyze duplicate companies: groups of (name_best, city) with 2+ active entries.
Categorize each group: NO-SITE, MULTI-SITE, NETWORK.
"""
import sys
sys.path.insert(0, 'G:\\Dev\\Projects\\GRANITE\\granite-crm-db')

from granite.database import Database, CompanyRow, EnrichedCompanyRow
from sqlalchemy import func

db = Database()
with db.session_scope() as session:
    # 1. Find (name_best, city) groups with 2+ active companies
    subq = (
        session.query(
            CompanyRow.name_best,
            CompanyRow.city,
            func.count(CompanyRow.id).label('cnt')
        )
        .filter(CompanyRow.deleted_at.is_(None))
        .filter(CompanyRow.merged_into.is_(None))
        .group_by(CompanyRow.name_best, CompanyRow.city)
        .having(func.count(CompanyRow.id) >= 2)
        .subquery()
    )

    # 2. Query full company rows for these groups, with enriched data
    rows = (
        session.query(CompanyRow)
        .join(
            subq,
            (CompanyRow.name_best == subq.c.name_best) &
            (CompanyRow.city == subq.c.city)
        )
        .filter(CompanyRow.deleted_at.is_(None))
        .filter(CompanyRow.merged_into.is_(None))
        .order_by(CompanyRow.name_best, CompanyRow.city, CompanyRow.id)
        .all()
    )

    # 3. Build groups
    groups = {}
    for r in rows:
        key = (r.name_best, r.city)
        if key not in groups:
            groups[key] = []
        groups[key].append(r)

    print(f'=== Found {len(groups)} duplicate groups (name_best + city with 2+ active) ===')
    print()

    # 4. For each group, get enriched data
    for (name_best, city), companies in sorted(groups.items()):
        print(f'=== Group: "{name_best}" / {city} ({len(companies)} entries) ===')

        # Get enriched rows
        enriched_ids = [c.id for c in companies]
        enriched_map = {}
        if enriched_ids:
            enriched_rows = (
                session.query(EnrichedCompanyRow)
                .filter(EnrichedCompanyRow.id.in_(enriched_ids))
                .all()
            )
            enriched_map = {e.id: e for e in enriched_rows}

        # Collect websites and is_network info
        websites = set()
        has_is_network = False
        for c in companies:
            w = (c.website or '').strip().lower()
            if w:
                websites.add(w)
            e = enriched_map.get(c.id)
            if e and e.is_network:
                has_is_network = True

        # Determine category
        if has_is_network:
            category = 'NETWORK'
        elif len(websites) >= 2:
            category = 'MULTI-SITE'
        elif len(websites) == 0:
            category = 'NO-SITE'
        else:
            category = 'SINGLE-SITE'

        print(f'  Category: {category}')
        if websites:
            sites_str = ', '.join(sorted(websites))
            print(f'  Unique sites ({len(websites)}): {sites_str}')
        else:
            print(f'  Sites: none')

        # Company details
        for c in companies:
            e = enriched_map.get(c.id)
            phone_count = len(c.phones) if isinstance(c.phones, list) else 0
            email_count = len(c.emails) if isinstance(c.emails, list) else 0
            is_net = e.is_network if e else False
            score = e.crm_score if e else 0
            seg = e.segment if e else 'N/A'
            site = c.website or '(none)'
            print(f'    [ID {c.id}] site={site} net={is_net} score={score} seg={seg} phones={phone_count} emails={email_count}')

        print()
