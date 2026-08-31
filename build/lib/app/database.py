"""SQLAlchemy-Engine, Session-Factory und deklarative Basis.

SQLite wird im WAL-Modus betrieben (bessere Nebenläufigkeit bei wenigen Nutzern)
und mit aktivierter Fremdschlüsselprüfung.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

settings.ensure_data_dir()

engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    connect_args={"check_same_thread": False},
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):  # noqa: ANN001
    """Für jede neue DB-Verbindung sinnvolle SQLite-PRAGMAs setzen."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Gemeinsame deklarative Basis aller ORM-Modelle."""


def get_db() -> Iterator[Session]:
    """FastAPI-Dependency: liefert eine Session und schließt sie danach."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
