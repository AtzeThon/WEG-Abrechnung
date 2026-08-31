"""Gemeinsame Test-Fixtures: isolierte SQLite-DB + eingeloggter TestClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  -- registriert Tabellen an Base.metadata
from app.database import Base, get_db
from app.main import app
from app.models import User


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
    admin = User(username="admin")
    admin.set_password("test1234")
    db_session.add(admin)
    db_session.commit()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        resp = c.post("/login", data={"username": "admin", "password": "test1234"})
        assert resp.status_code in (200, 303)
        yield c
    app.dependency_overrides.clear()
