"""Granite CRM API — минимальный FastAPI для аутрича.

Запуск: python cli.py api
   или: uvicorn granite.api.app:app --reload
"""
import os
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text as sa_text
from loguru import logger


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
    """
    env = os.environ.get("CORS_ORIGINS", "")
    if env:
        return [o.strip() for o in env.split(",") if o.strip()]
    return list(_DEFAULT_CORS_ORIGINS)


app = FastAPI(title="Granite CRM API", version="0.1.0", lifespan=lifespan)

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
        or request.method == "OPTIONS"
    ):
        return await call_next(request)

    expected_key = os.environ.get("GRANITE_API_KEY", "")
    if not expected_key:
        # Ключ не настроен — пропускаем без проверки (dev-режим)
        return await call_next(request)

    provided_key = request.headers.get("X-API-Key", "")
    if not provided_key or provided_key != expected_key:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing API key. Set X-API-Key header."},
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
