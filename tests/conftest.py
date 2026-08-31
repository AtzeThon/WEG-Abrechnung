"""Gemeinsame Test-Fixtures: isolierte SQLite-DB + TestClient.

Standardmäßig ist die Anwendung offen (kein Login). Für Login-Tests siehe die
Fixture ``login_required``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  -- registriert Tabellen an Base.metadata
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.templating import templates


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def login_required(monkeypatch):
    """Aktiviert den Verwalter-Login für einen Test."""
    monkeypatch.setattr(settings, "require_login", True)
    monkeypatch.setitem(templates.env.globals, "AUTH_ENABLED", True)
    yield
