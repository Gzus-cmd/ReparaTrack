"""T-10: primer corte vertical de infraestructura (config, esquema y salud)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect, text

from app.api.app import create_app
from app.api.deps import get_clock, get_session
from app.config import Settings
from app.db.base import Base


def test_health_reports_service_and_database_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_settings_defaults_match_spec_thresholds() -> None:
    settings = Settings()

    assert settings.warranty_days == 90
    assert settings.abandonment_days == 180
    assert settings.approval_days == 30
    assert settings.database_url


def test_settings_accept_environment_overrides(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("WARRANTY_DAYS", "120")
    monkeypatch.setenv("ABANDONMENT_DAYS", "200")
    monkeypatch.setenv("APPROVAL_DAYS", "45")

    settings = Settings.from_env()

    assert settings.database_url == "sqlite+pysqlite:///:memory:"
    assert settings.warranty_days == 120
    assert settings.abandonment_days == 200
    assert settings.approval_days == 45


def test_settings_keep_defaults_when_environment_is_empty(monkeypatch) -> None:
    for variable in ("DATABASE_URL", "WARRANTY_DAYS", "ABANDONMENT_DAYS", "APPROVAL_DAYS"):
        monkeypatch.delenv(variable, raising=False)

    settings = Settings.from_env()

    assert settings.warranty_days == 90
    assert settings.abandonment_days == 180
    assert settings.approval_days == 30


def test_app_creates_declared_schema_on_startup(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'reparatrack.db'}"
    app = create_app(settings=Settings(database_url=database_url))

    engine: Engine = app.state.engine
    tables = set(inspect(engine).get_table_names())

    assert tables == set(Base.metadata.tables)
    engine.dispose()


def test_app_exposes_engine_and_session_factory(settings: Settings) -> None:
    app = create_app(settings=settings)

    with app.state.session_factory() as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1

    app.state.engine.dispose()


def test_app_exposes_overridable_session_and_clock(
    settings: Settings, engine: Engine, session, clock
) -> None:
    app = create_app(settings=settings, engine=engine)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_clock] = lambda: clock

    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/health")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["database"] == "ok"
