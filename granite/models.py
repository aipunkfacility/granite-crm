# models.py
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from enum import Enum


class Source(str, Enum):
    FIRECRAWL = "firecrawl"
    JSPRAV = "jsprav"
    JSPRAV_PW = "jsprav_playwright"
    DGIS = "2gis"
    YELL = "yell"
    FIRMSRU = "firmsru"
    GOOGLE_MAPS = "google_maps"
    AVITO = "avito"


class CompanyStatus(str, Enum):
    RAW = "raw"
    VALIDATED = "validated"
    ENRICHED = "enriched"
    CONTACTED = "contacted"


class CompanySegment(str, Enum):
    DIGITAL_WORKSHOP = "Цифровая мастерская"    # has_cnc + has_production
    PRODUCER = "Производитель"                  # has_production, no portrait
    FULL_CYCLE = "Полный цикл"                  # has_production + portrait
    RESELLER = "Перекуп/Офис"                   # no production
    UNKNOWN = "Не определено"                   # нет данных с сайта


class RawCompany(BaseModel):
    """Сырые данные от любого скрепера. Единый формат для всех источников."""
    source: Source
    source_url: str = ""
    name: str
    phones: list[str] = Field(default_factory=list)  # E.164: 7XXXXXXXXXX
    address_raw: str = ""
    website: str | None = None
    emails: list[str] = Field(default_factory=list)
    geo: list[float] | None = None  # [lat, lon]
    messengers: dict[str, str] = Field(default_factory=dict)  # {"telegram": "...", "vk": "...", "whatsapp": "..."}
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    city: str = ""


class Company(BaseModel):
    """Компания после дедупликации. Основная таблица."""
    id: int | None = Field(default=None)  # auto-increment в SQLite
    merged_from: list[int] = Field(default_factory=list)  # RawCompany.id
    name_best: str
    phones: list[str] = Field(default_factory=list)  # объединённые уникальные
    address: str = ""
    website: str | None = None
    emails: list[str] = Field(default_factory=list)
    city: str = ""
    status: CompanyStatus = CompanyStatus.RAW
    segment: CompanySegment = CompanySegment.UNKNOWN
    needs_review: bool = False  # флаг для conflicts.md
    review_reason: str = ""     # причина пометки (например, "same_name_diff_address")
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

