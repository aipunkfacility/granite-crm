"""Helper to sync company_emails with CompanyRow.emails JSON.

Used by pipeline modules and API endpoints that write directly to CompanyRow.emails.
Call after setting CompanyRow.emails — diffs current company_emails against
the new JSON list: deletes removed, adds new, preserves existing.
"""
from granite.database import CompanyEmailRow


def sync_company_emails(session, company_id: int, emails_json: list[str] | None) -> None:
    """Sync company_emails to match the given JSON email list.

    Adds new emails (is_active=True, is_primary if first), removes deleted ones,
    preserves sent_count / is_active / is_primary on existing entries.
    """
    current = {
        e.email: e
        for e in session.query(CompanyEmailRow)
        .filter(CompanyEmailRow.company_id == company_id)
        .all()
    }

    if not emails_json:
        for row in current.values():
            session.delete(row)
        return

    new_set = {e.lower().strip() for e in emails_json if e and e.strip()}
    existing_emails = set(current.keys())

    for email, row in list(current.items()):
        if email not in new_set:
            session.delete(row)
            existing_emails.discard(email)

    has_existing = len(existing_emails) > 0
    first_new = True
    for email in emails_json:
        email_clean = email.lower().strip()
        if email_clean and email_clean not in existing_emails:
            session.add(CompanyEmailRow(
                company_id=company_id,
                email=email_clean,
                is_active=True,
                is_primary=(not has_existing and first_new),
            ))
            existing_emails.add(email_clean)
            first_new = False
