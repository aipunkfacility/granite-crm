from loguru import logger
from granite.database import Database, CompanyRow, EnrichedCompanyRow, RawCompanyRow


PLACEHOLDER_DOMAINS = {"email.com", "example.com"}


def _is_placeholder(email: str) -> bool:
    if not isinstance(email, str) or "@" not in email:
        return False
    domain = email.split("@", 1)[1].lower().strip()
    return domain in PLACEHOLDER_DOMAINS


def cleanup_placeholder_emails(
    db: Database,
    dry_run: bool = False,
    limit: int = 0,
) -> dict[str, int]:
    """Remove placeholder emails (@email.com, @example.com) from all company tables.

    Iterates raw_companies, companies, and enriched_companies.
    Returns dict with keys "raw", "companies", "enriched" — count of modified rows.
    If limit > 0, processes at most that many rows per table.
    """
    stats: dict[str, int] = {}

    for table_cls, key in [
        (RawCompanyRow, "raw"),
        (CompanyRow, "companies"),
        (EnrichedCompanyRow, "enriched"),
    ]:
        with db.session_scope() as session:
            rows = (
                session.query(table_cls)
                .filter(table_cls.emails.isnot(None))
                .all()
            )
            table_cleaned = 0
            for row in rows:
                if limit and table_cleaned >= limit:
                    break
                if not row.emails:
                    continue
                original = list(row.emails)
                cleaned = [e for e in original if not _is_placeholder(e)]
                if len(cleaned) != len(original):
                    table_cleaned += 1
                    removed = set(original) - set(cleaned)
                    logger.info(
                        f"  [{'DRY' if dry_run else 'UPD'}] {key} id={row.id}: "
                        f"removed {removed}, {len(original)}\u2192{len(cleaned)} emails"
                    )
                    if not dry_run:
                        row.emails = cleaned
        stats[key] = table_cleaned

    return stats
