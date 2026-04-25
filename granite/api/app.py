"""Granite CRM API — минимальный FastAPI для аутрича.

Запуск: python cli.py api
   или: uvicorn granite.api.app:app --reload
"""
import hmac
import os
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text as sa_text
from loguru import logger

from granite.api.schemas import ErrorResponse

# AUDIT #10: Rate limiting через in-memory счётчик.
# Для production рекомендуется заменить на slowapi + Redis.
import time
import threading
_rate_limit_store: dict[str, list[float]] = {}
_rate_limit_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация при старте, очистка при остановке."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    config_path = os.environ.get("GRANITE_CONFIG", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # FIX 1.1: Используем Database() вместо отдельного engine.
    # Database() уже настраивает WAL, FK, busy_timeout — DRY.
    # При одновременной работе пайплайна и API дефолтный DELETE-режим
    # вызывал "database is locked" — WAL решает это.
    from granite.database import Database
    db = Database(config_path=config_path)

    app.state.engine = db.engine
    app.state.Session = db.SessionLocal
    app.state.config = config
    app.state.db = db

    logger.info(f"CRM API started. DB: {db._db_path}")

    # Файловый лог с ротацией
    logger.add(
        "data/crm.log",
        rotation="10 MB",
        retention="30 days",
        level="INFO",
        encoding="utf-8",
    )

    yield

    # FIX MISS-11: Закрываем httpx.AsyncClient при shutdown.
    # Без этого — ResourceWarning: Unclosed client session в тестах и при перезагрузке.
    try:
        from granite.http_client import close_async_client
        await close_async_client()
    except Exception:
        pass

    db.engine.dispose()
    logger.info("CRM API stopped.")


# --- CORS: origins из env или дефолты ---

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def _get_cors_origins() -> list[str]:
    """Читает CORS origins из переменной окружения CORS_ORIGINS (comma-separated).

    Формат: CORS_ORIGINS=http://localhost:3000,http://myapp.ru
    Если переменная не задана — используются дефолтные origins.

    AUDIT #19: При использовании дефолтных origins выводится warning в лог,
    т.к. wildcard-origins в production небезопасны.
    """
    env = os.environ.get("CORS_ORIGINS", "")
    if env:
        return [o.strip() for o in env.split(",") if o.strip()]
    # AUDIT #19: Warning при использовании dev-дефолтов
    logger.warning(
        "CORS: using default localhost origins. "
        "Set CORS_ORIGINS env var for production."
    )
    return list(_DEFAULT_CORS_ORIGINS)


app = FastAPI(title="Granite CRM API", version="0.2.0", lifespan=lifespan)


# Phase 1.3: Стандартизированный exception handler для HTTPException.
# Все ошибки API возвращаются в формате ErrorResponse:
# {"error": "<сообщение>", "code": "<КОД>", "detail": null}
# Код ошибки маппится по HTTP-статусу, позволяя фронтенду программно
# обрабатывать сценарии без парсинга detail-строки.
_HTTP_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
}


@app.exception_handler(Exception)
async def standard_error_handler(request: Request, exc: Exception):
    """Глобальный fallback-обработчик для неперехваченных ошибок."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            code="INTERNAL_ERROR",
            detail=str(exc) if os.environ.get("DEBUG") else None,
        ).model_dump(),
    )


# Специфичные обработчики для HTTPException и RequestValidationError.
# FastAPI вызывает их до generic Exception handler.
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.exceptions import RequestValidationError


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    """Обработчик HTTPException — возвращает ErrorResponse."""
    code = _HTTP_STATUS_CODES.get(exc.status_code, "INTERNAL_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=str(exc.detail),
            code=code,
            detail=None,
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок валидации запроса — возвращает ErrorResponse.

    FIX: exc.errors() может содержать ValueError в ctx['error'], что не JSON-сериализуем.
    Конвертируем ошибки в JSON-безопасный формат перед передачей в ErrorResponse.
    """
    # Конвертируем ошибки в JSON-безопасный формат
    safe_errors = []
    for err in exc.errors():
        safe_err = {
            "type": err.get("type", ""),
            "loc": err.get("loc", ()),
            "msg": err.get("msg", ""),
            "input": err.get("input"),
        }
        # ctx может содержать ValueError — конвертируем в строку
        ctx = err.get("ctx")
        if ctx:
            safe_err["ctx"] = {k: str(v) for k, v in ctx.items()}
        safe_errors.append(safe_err)

    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error="Validation error",
            code="VALIDATION_ERROR",
            detail=safe_errors,
        ).model_dump(),
    )

# AUDIT #10: Rate limiting middleware (in-memory).
# Лимиты по умолчанию: send=10/мин, run campaign=3/мин, export=20/мин.
# Настраивается через RATE_LIMITS env (JSON).
_RATE_LIMITS = {
    "post:/companies/.*?/send": (10, 60),
    "post:/campaigns/.*?/run": (3, 60),
    "get:/export/.*": (20, 60),
}


def _parse_rate_limits_from_env() -> dict:
    """AUDIT #10: Читает rate limits из env RATE_LIMITS (JSON).

    Формат: {"post:/companies/1/send": [10, 60], ...}
    """
    env = os.environ.get("RATE_LIMITS", "")
    if not env:
        return {}
    try:
        import json
        parsed = json.loads(env)
        if isinstance(parsed, dict):
            result = {}
            for pattern, val in parsed.items():
                if isinstance(val, list) and len(val) == 2:
                    result[pattern] = (int(val[0]), int(val[1]))
            return result
    except Exception:
        pass
    return {}


_ENV_LIMITS = _parse_rate_limits_from_env()
if _ENV_LIMITS:
    _RATE_LIMITS.update(_ENV_LIMITS)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """AUDIT #10: Простой rate limiter — in-memory, по IP + endpoint.

    Для каждого {method}:{path} считает количество запросов за окно.
    При превышении — 429 Too Many Requests.
    """
    key = f"{request.method.lower()}:{request.url.path}"
    client_ip = request.client.host if request.client else "unknown"

    # Проверяем, попал ли запрос под лимит
    for pattern, (max_requests, window_sec) in _RATE_LIMITS.items():
        import re as _re
        if _re.match(pattern, key):
            now = time.time()
            bucket_key = f"{client_ip}:{pattern}"
            with _rate_limit_lock:
                timestamps = _rate_limit_store.get(bucket_key, [])
                # Очищаем старые записи за пределами окна
                timestamps = [t for t in timestamps if now - t < window_sec]
                if len(timestamps) >= max_requests:
                    return JSONResponse(
                        status_code=429,
                        content=ErrorResponse(
                            error=f"Rate limit exceeded: {max_requests} requests per {window_sec}s",
                            code="RATE_LIMITED",
                        ).model_dump(),
                    )
                timestamps.append(now)
                _rate_limit_store[bucket_key] = timestamps
            break

    return await call_next(request)


# FIX K2: Ограничиваем CORS-методы и заголовки вместо wildcard.
# Ранее allow_methods=["*"] и allow_headers=["*"] позволяли
# любые HTTP-методы и заголовки, что избыточно для CRM API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "Accept"],
    allow_credentials=True,
)


# FIX K1: API-key аутентификация.
# Если переменная GRANITE_API_KEY не задана — аутентификация отключена (dev-режим).
# Если задана — все /api/v1/* запросы требуют заголовок X-API-Key.
# /health, /docs, /openapi.json, /redoc — доступны без ключа.
@app.middleware("http")
async def api_key_auth_middleware(request: Request, call_next):
    # Пропускаем без аутентификации:
    # - non-API маршруты (health, docs, openapi.json, redoc)
    # - OPTIONS (preflight для CORS)
    skip_paths = ("/health", "/docs", "/openapi.json", "/redoc")
    if (
        not request.url.path.startswith("/api/v1/")
        or request.url.path in skip_paths
        or request.url.path.startswith("/api/v1/track/")
        or request.method == "OPTIONS"
    ):
        return await call_next(request)

    expected_key = os.environ.get("GRANITE_API_KEY", "")
    if not expected_key:
        # Ключ не настроен — пропускаем без проверки (dev-режим)
        return await call_next(request)

    provided_key = request.headers.get("X-API-Key", "")
    if not provided_key or not hmac.compare_digest(provided_key, expected_key):
        return JSONResponse(
            status_code=401,
            content=ErrorResponse(
                error="Invalid or missing API key. Set X-API-Key header.",
                code="UNAUTHORIZED",
            ).model_dump(),
        )

    return await call_next(request)

from granite.api import (
    companies, touches, tasks, tracking, campaigns,
    followup, funnel, messenger, templates, stats, export,
)
app.include_router(companies.router, prefix="/api/v1", tags=["companies"])
app.include_router(touches.router, prefix="/api/v1", tags=["touches"])
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(tracking.router, prefix="/api/v1", tags=["tracking"])
app.include_router(campaigns.router, prefix="/api/v1", tags=["campaigns"])
app.include_router(followup.router, prefix="/api/v1", tags=["followup"])
app.include_router(funnel.router, prefix="/api/v1", tags=["funnel"])
app.include_router(messenger.router, prefix="/api/v1", tags=["messenger"])
app.include_router(templates.router, prefix="/api/v1", tags=["templates"])
app.include_router(stats.router, prefix="/api/v1", tags=["stats"])
app.include_router(export.router, prefix="/api/v1", tags=["export"])

from granite.api import pipeline_status
app.include_router(pipeline_status.router, prefix="/api/v1", tags=["pipeline"])


@app.get("/health")
def health(request: Request):
    """Health check с пингом БД."""
    db_ok = False
    try:
        session = request.app.state.Session()
        session.execute(sa_text("SELECT 1"))
        session.close()
        db_ok = True
    except Exception:
        pass
    status = "ok" if db_ok else "degraded"
    return {"status": status, "db": db_ok}
