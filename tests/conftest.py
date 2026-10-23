"""Fixtures compartidas: app, engine, sesión, reloj congelado y cliente HTTP.

Cada test recibe una base SQLite en memoria nueva (aislamiento total) y un
reloj congelado; ninguna fixture usa `datetime.now()` ni toca la BD real.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from support.clock import FrozenClock

from app.api.app import create_app
from app.api.deps import get_clock, get_session
from app.config import Settings
from app.db.base import Base
from app.db.session import create_engine_from_url

MEMORY_DATABASE_URL = "sqlite+pysqlite:///:memory:"


@pytest.fixture
def settings() -> Settings:
    """Configuración de prueba con los umbrales de la spec."""
    return Settings(database_url=MEMORY_DATABASE_URL)


@pytest.fixture
def engine(settings: Settings) -> Iterator[Engine]:
    """Motor SQLite en memoria con el esquema creado y destruido por test."""
    engine = create_engine_from_url(settings.database_url)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Sesión ligada al motor; rollback y cierre en teardown."""
    with Session(engine) as session:
        try:
            yield session
        finally:
            session.rollback()


@pytest.fixture
def clock() -> FrozenClock:
    """Reloj congelado en 2026-10-22 15:00 UTC."""
    return FrozenClock(datetime(2026, 10, 22, 15, 0, tzinfo=UTC))


@pytest.fixture
def client(
    settings: Settings, engine: Engine, session: Session, clock: FrozenClock
) -> Iterator[TestClient]:
    """`TestClient` con la sesión y el reloj del test inyectados."""
    app = create_app(settings=settings, engine=engine)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_clock] = lambda: clock
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
