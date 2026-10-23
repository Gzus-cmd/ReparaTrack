"""Fábrica de la aplicación FastAPI (composición de capas)."""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import Engine

from app.api.router import api_router
from app.config import Settings
from app.db import models as _models  # noqa: F401  (registra las tablas en el metadata)
from app.db.base import Base
from app.db.session import create_engine_from_url, create_session_factory


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    """Crea la app, registra los routers y materializa el esquema (D-08).

    `engine` permite inyectar el motor de los tests sin tocar la base real; la
    sesión y el reloj se sobrescriben con `dependency_overrides`.
    """
    resolved_settings = settings or Settings.from_env()
    resolved_engine = engine or create_engine_from_url(resolved_settings.database_url)
    Base.metadata.create_all(resolved_engine)

    app = FastAPI(
        title="ReparaTrack API",
        version="0.1.0",
        description="Sistema de trazabilidad de soporte técnico (TerabyteRS).",
    )
    app.state.settings = resolved_settings
    app.state.engine = resolved_engine
    app.state.session_factory = create_session_factory(resolved_engine)
    app.include_router(api_router, prefix="/api/v1")
    return app
