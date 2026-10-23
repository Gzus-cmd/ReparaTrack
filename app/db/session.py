"""Motor y fábrica de sesiones SQLite.

SQLite necesita `PRAGMA foreign_keys=ON` en cada conexión para que las FK con
`ON DELETE RESTRICT` se apliquen de verdad; las bases en memoria comparten una
única conexión con `StaticPool` para sobrevivir entre sesiones.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_MEMORY_MARKERS = (":memory:", "mode=memory")


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """Activa la verificación de claves foráneas en SQLite."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def create_engine_from_url(database_url: str) -> Engine:
    """Crea el motor configurado para SQLite (memoria o archivo)."""
    options: dict[str, object] = {"future": True}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if any(marker in database_url for marker in _MEMORY_MARKERS):
            options["poolclass"] = StaticPool
    engine = create_engine(database_url, **options)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Fábrica de sesiones con flush explícito en los repositorios."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
