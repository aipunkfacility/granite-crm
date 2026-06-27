#!/usr/bin/env python3
"""Одноразовый скрипт: пометить все компании с @vsepamyatniki.ru как сеть.

Usage:
    uv run python scripts/mark_vsepamyatniki_network.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from granite.database import Database, EnrichedCompanyRow, NetworkRow
from granite.utils import extract_domain
from loguru import logger
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


def mark_network(session=None) -> None:
    db = Database()
    own_session = False
    if session is None:
        session = db.get_session()
        own_session = True

    try:
        rows = session.query(EnrichedCompanyRow).filter(
            EnrichedCompanyRow.emails.contains("vsepamyatniki.ru")
        ).all()

        if not rows:
            logger.warning("No companies with @vsepamyatniki.ru found.")
            return

        logger.info(f"Found {len(rows)} companies with @vsepamyatniki.ru")

        member_ids = set()
        emails_all = set()
        phones_all = set()
        subdomains = set()
        cities = set()
        names = []
        segments = []
        scores = []

        for r in rows:
            member_ids.add(r.id)
            if r.emails:
                for e in (json.loads(r.emails) if isinstance(r.emails, str) else r.emails):
                    emails_all.add(e)
            if r.phones:
                for p in (json.loads(r.phones) if isinstance(r.phones, str) else r.phones):
                    phones_all.add(p)
            if r.website:
                dom = extract_domain(r.website)
                if dom:
                    subdomains.add(dom)
            if r.city:
                cities.add(r.city)
            names.append(r.name or "")
            if r.segment:
                segments.append(r.segment)
            if r.crm_score:
                scores.append(r.crm_score)

        now = datetime.now(timezone.utc)

        stmt = sqlite_insert(NetworkRow).values(
            name="ВсеПамятники / vsepamyatniki.ru",
            base_domain="vsepamyatniki.ru",
            signal_type="email_domain",
            network_type="franchise",
            subdomains=json.dumps(sorted(subdomains), ensure_ascii=False),
            emails=json.dumps(sorted(emails_all), ensure_ascii=False),
            phones=json.dumps(sorted(phones_all), ensure_ascii=False),
            company_count=len(member_ids),
            city_count=len(cities),
            cities=json.dumps(sorted(cities), ensure_ascii=False),
            avg_score=sum(scores) / len(scores) if scores else 0.0,
            segment_dist=json.dumps(
                {s: segments.count(s) for s in set(segments)},
                ensure_ascii=False,
            ),
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["base_domain"],
            set_={
                "name": stmt.excluded.name,
                "signal_type": stmt.excluded.signal_type,
                "network_type": stmt.excluded.network_type,
                "subdomains": stmt.excluded.subdomains,
                "emails": stmt.excluded.emails,
                "phones": stmt.excluded.phones,
                "company_count": stmt.excluded.company_count,
                "city_count": stmt.excluded.city_count,
                "cities": stmt.excluded.cities,
                "avg_score": stmt.excluded.avg_score,
                "segment_dist": stmt.excluded.segment_dist,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        session.execute(stmt)
        session.flush()

        network = session.query(NetworkRow).filter(
            NetworkRow.base_domain == "vsepamyatniki.ru"
        ).first()

        session.query(EnrichedCompanyRow).filter(
            EnrichedCompanyRow.id.in_(list(member_ids))
        ).update(
            {
                EnrichedCompanyRow.is_network: True,
                EnrichedCompanyRow.network_id: network.id,
            },
            synchronize_session=False,
        )

        session.commit()
        logger.info(
            f"Marked {len(member_ids)} companies as network 'vsepamyatniki.ru' "
            f"(id={network.id}, cities={len(cities)})"
        )

    except Exception:
        logger.exception("Failed to mark vsepamyatniki network")
        if own_session:
            session.rollback()
        raise
    finally:
        if own_session:
            session.close()


if __name__ == "__main__":
    mark_network()
