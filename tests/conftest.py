"""Общие pytest-фикстуры для CRM API тестов.

Вынесено из test_crm_api.py для переиспользования во всех тестовых файлах.
"""
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from granite.api.deps import get_db
from granite.database import Base


# Тестовые шаблоны для TemplateRegistry (минимальный набор)
_TEST_TEMPLATES = [
    {
        "name": "follow_up_email_v1",
        "channel": "email",
        "subject": "Re: {original_subject}",
        "body": "Follow-up for {city}. Unsub: {unsubscribe_url}",
        "body_type": "plain",
        "description": "System required template",
    },
    {
        "name": "cold_email_v1",
        "channel": "email",
        "subject": "Offer for {city}",
        "body": "Hello {from_name} in {city}. Unsub: {unsubscribe_url}",
        "body_type": "plain",
        "description": "Cold email v1",
    },
    {
        "name": "cold_email_1",
        "channel": "email",
        "subject": "Test",
        "body": "Hello {from_name}. Unsub: {unsubscribe_url}",
        "body_type": "plain",
        "description": "Legacy test template (from old seed)",
    },
    {
        "name": "tg_intro",
        "channel": "tg",
        "subject": "",
        "body": "Hi {from_name}",
        "body_type": "plain",
        "description": "TG intro",
    },
    {
        "name": "reply_price",
        "channel": "email",
        "subject": "Re: {original_subject}",
        "body": "Цена ретуши: от 700 руб. Примеры: retouchgrav.netlify.app. Unsub: {unsubscribe_url}",
        "body_type": "plain",
        "description": "Reply template — price",
    },
]


@pytest.fixture
def engine():
    """In-memory SQLite с FK PRAGMA. Используется shared StaticPool."""
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(_engine, "connect")
    def _pragma(dbapi_conn, conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(_engine)
    yield _engine
    _engine.dispose()


@pytest.fixture
def db_session(engine):
    """Прямая сессия БД для расстановки тестовых данных (без TestClient).

    NOTE: данные нужно явно commit() перед API-вызовами через client,
    т.к. client использует свою сессию через dependency_overrides.
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def client(engine, monkeypatch, tmp_path):
    """TestClient с in-memory БД, TemplateRegistry и dependency override."""
    import os
    # Установить рабочий каталог проекта, чтобы lifespan нашёл config.yaml
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    monkeypatch.chdir(project_root)

    from granite.api.app import app
    from granite.templates import TemplateRegistry

    TestSession = sessionmaker(bind=engine)

    # Записываем тестовые шаблоны во временный JSON
    test_json = tmp_path / "test_templates.json"
    with open(test_json, "w", encoding="utf-8") as f:
        json.dump(_TEST_TEMPLATES, f, ensure_ascii=False)

    def get_test_db():
        session = TestSession()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # FIX BUG-5: Сохраняем оригинальные значения app.state
    original_session = getattr(app.state, 'Session', None)
    original_registry = getattr(app.state, 'template_registry', None)

    app.dependency_overrides[get_db] = get_test_db
    app.state.Session = TestSession
    app.state.template_registry = TemplateRegistry(str(test_json))

    try:
        with TestClient(app) as c:
            # Переписываем template_registry ПОСЛЕ lifespan (который создаёт свой)
            app.state.template_registry = TemplateRegistry(str(test_json))
            yield c
    finally:
        app.dependency_overrides.clear()
        app.state.Session = original_session
        app.state.template_registry = original_registry
