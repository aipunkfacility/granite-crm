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
    geo: tuple[float, float] | None = None  # (lat, lon)
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


# DEPRECATED: EnrichedCompany — не используется в текущем пайплайне (используется EnrichedCompanyRow из database.py)
class EnrichedCompany(BaseModel):
    """Компания после обогащения мессенджерами и сегментацией."""
    company_id: int  # Company.id
    telegram: str | None = None       # https://t.me/username
    whatsapp: str | None = None       # https://wa.me/7XXXXXXXXXX
    vk: str | None = None             # https://vk.com/...
    ok: str | None = None             # https://ok.ru/...
    has_production: bool = False
    has_cnc: bool = False
    has_portrait_service: bool = False
    is_site_constructor: bool = False  # Tilda/Wix/uCoz/и т.д.
    tech_keywords_found: list[str] = Field(default_factory=list)
    is_network: bool = False
    network_cities: list[str] = Field(default_factory=list)
    priority_score: int = 0
    tg_has_description: bool = False  # есть описание в TG-профиле
    tg_has_avatar: bool = False       # есть аватар в TG-профиле
    website_status: int | None = None  # HTTP статус сайта (200, 404, None)
    map_rating: float | None = None   # рейтинг на картах
    map_reviews_count: int | None = None


class PipelineRun(BaseModel):
    """Запись о запуске pipeline для отслеживания прогресса."""
    id: int | None = Field(default=None)
    city: str
    stage: str              # "ingest" | "dedup" | "enrich" | "full"
    source: str | None = None  # конкретный источник (если применимо)
    started_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    finished_at: datetime | None = None
    records_found: int = 0
    records_errors: int = 0
    status: str = "running"  # "running" | "completed" | "failed"
    error_message: str = ""
