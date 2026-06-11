"""One-time migration: populate company_emails from companies.emails JSON.

Usage:
    uv run python scripts/migrate_company_emails.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from granite.database import Database, CompanyEmailRow, CompanyRow, CrmEmailLogRow


def migrate():
    db = Database()

    with db.session_scope() as session:
        existing_count = session.query(CompanyEmailRow).count()
        if existing_count > 0:
            print(f"Migration already run ({existing_count} emails found). Skipping.")
            return

        companies = (
            session.query(CompanyRow)
            .filter(CompanyRow.merged_into.is_(None))
            .all()
        )

        total_inserted = 0
        total_skipped = 0

        for company in companies:
            emails = company.emails or []
            if not emails:
                total_skipped += 1
                continue

            seen = set()
            for email in emails:
                email_clean = email.lower().strip()
                if not email_clean or email_clean in seen:
                    continue
                seen.add(email_clean)

                was_sent = session.query(CrmEmailLogRow).filter(
                    CrmEmailLogRow.email_to == email_clean,
                    CrmEmailLogRow.company_id == company.id,
                    CrmEmailLogRow.status.in_(("sent", "opened", "replied", "bounced")),
                ).first() is not None

                session.add(CompanyEmailRow(
                    company_id=company.id,
                    email=email_clean,
                    is_active=not was_sent,
                    is_primary=(len(seen) == 1),
                    sent_count=1 if was_sent else 0,
                ))
                total_inserted += 1

    print(f"Migrated {total_inserted} emails (skipped {total_skipped} companies with no emails)")


if __name__ == "__main__":
    migrate()
