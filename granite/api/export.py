"""Export API: HTTP-экспорт enriched-данных города в CSV.

GET /api/v1/export/{city}.csv — отдаёт CSV с обогащёнными данными
для указанного города. Формат идентичен файловому экспорту из
pipeline/export_phase.py, но отдаётся напрямую через HTTP.
"""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from granite.api.deps import get_db
from granite.database import CompanyRow, EnrichedCompanyRow
from granite.utils import sanitize_filename

__all__ = ["router"]

router = APIRouter()

_CSV_FIELDS = [
    "id", "name", "phones", "address", "website", "emails",
    "city", "region",
    "segment", "crm_score", "is_network", "cms", "has_marquiz",
    "telegram", "vk", "whatsapp",
]


def _build_csv_row(enriched: EnrichedCompanyRow, company: CompanyRow) -> dict:
    """Собрать строку CSV из EnrichedCompanyRow + CompanyRow."""
    messengers = enriched.messengers or {}
    return {
        "id": enriched.id,
        "name": enriched.name or company.name_best,
        "phones": "; ".join(enriched.phones or []),
        "address": enriched.address_raw or "",
        "website": enriched.website or company.website or "",
        "emails": "; ".join(enriched.emails or []),
        "city": enriched.city,
        "region": enriched.region or company.region or "",
        "segment": enriched.segment or "",
        "crm_score": enriched.crm_score or 0,
        "is_network": "Yes" if enriched.is_network else "No",
        "cms": enriched.cms or "",
        "has_marquiz": "Yes" if enriched.has_marquiz else "No",
        "telegram": messengers.get("telegram", ""),
        "vk": messengers.get("vk", ""),
        "whatsapp": messengers.get("whatsapp", ""),
    }


@router.get("/export/{city}.csv")
def export_city_csv(city: str, db: Session = Depends(get_db)):
    """Экспорт enriched-данных города в CSV.

    Возвращает CSV-файл с обогащёнными данными для указанного города.
    Формат идентичен файловому экспорту из pipeline/export_phase.py.
    Сортировка по crm_score DESC.
    """
    rows = (
        db.query(EnrichedCompanyRow, CompanyRow)
        .join(CompanyRow, EnrichedCompanyRow.id == CompanyRow.id)
        .filter(EnrichedCompanyRow.city == city)
        .filter(EnrichedCompanyRow.crm_score > 0)
        .order_by(EnrichedCompanyRow.crm_score.desc())
        .all()
    )

    if not rows:
        raise HTTPException(404, f"No enriched data found for city '{city}'")

    # Строим CSV в памяти через StringIO
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_CSV_FIELDS)
    writer.writeheader()
    for enriched, company in rows:
        writer.writerow(_build_csv_row(enriched, company))

    # Формируем ответ
    safe_city = sanitize_filename(city)
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_city}_enriched.csv"',
        },
    )
