"""Fix: deactivate company_emails that were sent from OTHER companies.

Data migration (Task 1) only checked CrmEmailLogRow for (company_id, email),
missing cross-company sends. This script catches the rest.

Usage:
    uv run python scripts/fix_company_emails_cross_company.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from granite.database import Database, CompanyEmailRow, CrmEmailLogRow


def fix():
    db = Database()
    with db.session_scope() as session:
        # 1. Все email, на которые когда-либо отправляли (любая компания)
        sent_emails = set(
            row[0]
            for row in session.query(CrmEmailLogRow.email_to)
            .filter(CrmEmailLogRow.status.in_(("sent", "opened", "replied", "bounced")))
            .distinct()
            .all()
        )

        if not sent_emails:
            print("Нет отправленных писем в логах. Нечего делать.")
            return

        # 2. Активные company_emails, email которых есть в sent_emails
        affected = (
            session.query(CompanyEmailRow)
            .filter(
                CompanyEmailRow.is_active == True,
                CompanyEmailRow.email.in_(sent_emails),
            )
            .all()
        )

        if not affected:
            print("Нет активных company_emails для деактивации.")
            return

        print(f"Найдено {len(affected)} активных записей для уже отправленных email-адресов")

        # 3. Деактивация + сбор компаний, потерявших primary
        lost_primary: set[int] = set()
        for ce in affected:
            if ce.is_primary:
                ce.is_primary = False
                lost_primary.add(ce.company_id)
            ce.is_active = False

        # 4. Назначить новый primary для компаний, потерявших его
        for company_id in lost_primary:
            next_active = (
                session.query(CompanyEmailRow)
                .filter(
                    CompanyEmailRow.company_id == company_id,
                    CompanyEmailRow.is_active == True,
                )
                .order_by(CompanyEmailRow.id)
                .first()
            )
            if next_active:
                next_active.is_primary = True

        print(f"Деактивировано {len(affected)} записей, {len(lost_primary)} компаний потеряли primary")


if __name__ == "__main__":
    fix()
