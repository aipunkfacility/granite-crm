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

        network = session.query(NetworkRow).filter(
            NetworkRow.base_domain == "vsepamyatniki.ru"
        ).first()
        if network:
            network.name = "ВсеПамятники / vsepamyatniki.ru"
            network.network_type = "franchise"
            network.subdomains = sorted(subdomains)
            network.emails = sorted(emails_all)
            network.phones = sorted(phones_all)
            network.company_count = len(member_ids)
            network.city_count = len(cities)
            network.cities = sorted(cities)
            network.avg_score = sum(scores) / len(scores) if scores else 0.0
            network.segment_dist = {s: segments.count(s) for s in set(segments)}
            network.updated_at = now
        else:
            network = NetworkRow(
                name="ВсеПамятники / vsepamyatniki.ru",
                base_domain="vsepamyatniki.ru",
                signal_type="email_domain",
                network_type="franchise",
                subdomains=sorted(subdomains),
                emails=sorted(emails_all),
                phones=sorted(phones_all),
                company_count=len(member_ids),
                city_count=len(cities),
                cities=sorted(cities),
                avg_score=sum(scores) / len(scores) if scores else 0.0,
                segment_dist={s: segments.count(s) for s in set(segments)},
                created_at=now,
                updated_at=now,
            )
            session.add(network)
        session.flush()

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
