"""Общие pytest-фикстуры для CRM API тестов.

Вынесено из test_crm_api.py для переиспользования во всех тестовых файлах.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from granite.api.deps import get_db
from granite.database import Base, CrmTemplateRow


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
def client(engine):
    """TestClient с in-memory БД, сидом шаблонов и dependency override."""
    from granite.api.app import app

    TestSession = sessionmaker(bind=engine)

    # Seed шаблоны
    with TestSession() as s:
        s.add(CrmTemplateRow(
            name="cold_email_1", channel="email",
            subject="Test", body="Hello {from_name}",
        ))
        s.add(CrmTemplateRow(
            name="tg_intro", channel="tg",
            subject="", body="Hi {from_name}",
        ))
        s.commit()

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

    # FIX BUG-5: Сохраняем оригинальное значение app.state.Session
    # и восстанавливаем после теста. app — синглтон модуля, без этого
    # значение «утекает» между тестами (особенно с pytest-xdist).
    original_session = getattr(app.state, 'Session', None)

    app.dependency_overrides[get_db] = get_test_db
    app.state.Session = TestSession

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        app.state.Session = original_session
