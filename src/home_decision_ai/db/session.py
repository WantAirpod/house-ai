from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from home_decision_ai.settings import get_settings


def build_engine():
    settings = get_settings()
    if not settings.database_url:
        msg = "DATABASE_URL is required for database operations."
        raise RuntimeError(msg)
    return create_engine(settings.database_url, pool_pre_ping=True)


engine = None
SessionLocal: sessionmaker[Session] | None = None


def configure_database() -> None:
    global engine, SessionLocal
    engine = build_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Iterator[Session]:
    if SessionLocal is None:
        configure_database()
    assert SessionLocal is not None
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
