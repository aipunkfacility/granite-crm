"""Pydantic схемы для валидации API запросов и ответов.

FIX M4: Добавлены Response-модели для всех эндпоинтов.
Это позволяет FastAPI генерировать корректную OpenAPI-документацию
и автогенерировать TypeScript-типы через openapi-typescript.

FIX M5: Добавлен PaginatedResponse — единая обёртка для всех списков.
"""
from typing import Optional, Any, List

from pydantic import BaseModel, Field


# ============================================================
# Request-модели (валидация входящих данных)
# ============================================================

class CreateTouchRequest(BaseModel):
    channel: str = Field(..., pattern="^(email|tg|wa|manual)$")
    direction: str = Field("outgoing", pattern="^(outgoing|incoming)$")
    subject: str = ""
    body: str = ""
    note: str = ""


class UpdateCompanyRequest(BaseModel):
    funnel_stage: Optional[str] = Field(
        None,
        pattern="^(new|email_sent|email_opened|tg_sent|wa_sent|replied|interested|not_interested|unreachable)$",
    )
    notes: Optional[str] = None
    stop_automation: Optional[bool] = None


class CreateTaskRequest(BaseModel):
    title: str = Field("Follow-up", min_length=1)
    description: str = ""
    due_date: Optional[str] = None  # ISO format, validated in endpoint
    priority: str = Field("normal", pattern="^(low|normal|high)$")
    task_type: str = Field("follow_up", pattern="^(follow_up|send_portfolio|send_test_offer|check_response|other)$")


class UpdateTaskRequest(BaseModel):
    status: Optional[str] = Field(None, pattern="^(pending|in_progress|done|cancelled)$")
    priority: Optional[str] = Field(None, pattern="^(low|normal|high)$")
    title: Optional[str] = Field(None, min_length=1)


# AUDIT #21: CampaignFilters — типизированная схема для campaign filters.
# Ранее filters: dict принимал любые ключи без валидации.
class CampaignFilters(BaseModel):
    """Фильтры кампании: город, сегмент, минимальный скор."""
    city: Optional[str] = None
    segment: Optional[str] = Field(None, pattern="^(A|B|C|D|spam)$")
    min_score: Optional[int] = Field(None, ge=0, le=200)


class CreateCampaignRequest(BaseModel):
    name: str = Field("Campaign", min_length=1)
    template_name: str = Field("cold_email_1", min_length=1)
    filters: CampaignFilters = Field(default_factory=CampaignFilters)


class UpdateCampaignRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    template_name: Optional[str] = Field(None, min_length=1)


class CreateTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, pattern=r"^[a-z0-9_]+$")
    channel: str = Field(..., pattern="^(email|tg|wa)$")
    subject: str = ""
    body: str = Field(..., min_length=1)
    description: str = ""


class UpdateTemplateRequest(BaseModel):
    channel: Optional[str] = Field(None, pattern="^(email|tg|wa)$")
    subject: Optional[str] = None
    body: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None


class SendMessageRequest(BaseModel):
    channel: str = Field(..., pattern="^(tg|wa)$")
    template_name: Optional[str] = None
    text: Optional[str] = None


class PipelineRunRequest(BaseModel):
    """Запрос на запуск пайплайна для города."""
    city: str = Field(..., min_length=1, description="Название города или 'all'")
    force: bool = Field(False, description="Очистить старые данные")
    re_enrich: bool = Field(False, description="Только обогащение")


class MergeRequest(BaseModel):
    """Запрос на слияние компаний."""
    source_ids: List[int] = Field(..., min_length=1, description="ID компаний для слияния в текущую")


# ============================================================
# Response-модели (документирование OpenAPI-ответов)
# ============================================================


class OkResponse(BaseModel):
    """Универсальный ответ {ok: true, ...}.

    FIX BUG-C1: Добавлены поля warnings и message.
    templates.py передаёт warnings при создании/обновлении шаблонов.
    """
    ok: bool = True
    warnings: Optional[List[str]] = None
    message: Optional[str] = None


class OkWithIdResponse(BaseModel):
    """Ответ с ID созданного объекта."""
    ok: bool = True
    id: Optional[int] = Field(None, description="ID созданного объекта")


class CompanyResponse(BaseModel):
    """Карточка компании — используется в list и get."""
    id: int
    name: str
    phones: list[str] = []
    website: Optional[str] = None
    emails: list[str] = []
    city: str
    region: str = ""
    messengers: dict = {}
    telegram: Optional[str] = None
    whatsapp: Optional[str] = None
    vk: Optional[str] = None
    segment: Optional[str] = None
    crm_score: int = 0
    cms: Optional[str] = None
    has_marquiz: bool = False
    is_network: bool = False
    tg_trust: dict = {}
    funnel_stage: str = "new"
    email_sent_count: int = 0
    email_opened_count: int = 0
    tg_sent_count: int = 0
    wa_sent_count: int = 0
    last_contact_at: Optional[str] = None
    notes: str = ""
    stop_automation: bool = False

    model_config = {"from_attributes": True}


class TouchResponse(BaseModel):
    """Запись о касании."""
    id: int
    company_id: int
    channel: str
    direction: str
    subject: str = ""
    body: str = ""
    note: str = ""
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    """Задача."""
    id: int
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    company_city: Optional[str] = None
    title: str
    task_type: str
    priority: str
    status: str
    due_date: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class TaskDetailResponse(BaseModel):
    """Задача (без join-данных о компании)."""
    id: int
    title: str
    task_type: str
    priority: str
    status: str
    due_date: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class TemplateResponse(BaseModel):
    """Шаблон сообщения."""
    name: str
    channel: str
    subject: str = ""
    body: str
    description: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}


class CampaignResponse(BaseModel):
    """Кампания (в списке)."""
    id: int
    name: str
    template_name: str
    status: str
    total_sent: int = 0
    total_opened: int = 0
    total_replied: int = 0
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class CampaignDetailResponse(BaseModel):
    """Детали кампании + предпросмотр получателей."""
    id: int
    name: str
    template_name: str
    status: str
    filters: dict = {}
    total_sent: int = 0
    total_opened: int = 0
    preview_recipients: int = 0

    model_config = {"from_attributes": True}


class CampaignStatsResponse(BaseModel):
    """Статистика кампании."""
    id: int
    name: str
    status: str
    total_sent: int = 0
    total_opened: int = 0
    total_replied: int = 0
    open_rate: float = 0.0

    model_config = {"from_attributes": True}


class FollowupItemResponse(BaseModel):
    """Элемент очереди follow-up."""
    company_id: int
    name: str
    city: str
    region: str = ""
    funnel_stage: str
    days_since_last_contact: int
    recommended_channel: str
    channel_available: bool
    template_name: str
    action: str
    telegram: Optional[str] = None
    whatsapp: Optional[str] = None
    emails: list[str] = []
    crm_score: int = 0
    segment: str = "D"

    model_config = {"from_attributes": True}


class FunnelResponse(BaseModel):
    """Распределение по стадиям воронки."""
    model_config = {"extra": "allow"}

    # Динамические ключи: new, email_sent, ..., unreachable -> int


class StatsResponse(BaseModel):
    """Агрегированная статистика CRM."""
    total_companies: int = 0
    funnel: dict[str, int] = {}
    segments: dict[str, int] = {}
    top_cities: list[dict[str, Any]] = []
    with_telegram: int = 0
    with_whatsapp: int = 0
    with_email: int = 0

    model_config = {"from_attributes": True}


class MessengerResultResponse(BaseModel):
    """Результат отправки через мессенджер."""
    ok: bool
    channel: Optional[str] = None
    contact_id: Optional[str] = None
    error: Optional[str] = None


# FIX M5: Универсальная обёртка для пагинированных списков.
# Используется всеми list-эндпоинтами для согласованного формата ответа.
class PaginatedResponse(BaseModel):
    """Стандартный ответ для пагинированных списков."""
    items: list[Any] = []
    total: int = 0
    page: int = 1
    per_page: int = 50
