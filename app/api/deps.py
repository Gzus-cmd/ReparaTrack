"""Dependencias HTTP: sesión de base de datos y reloj inyectable."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.services.ports import Clock


class SystemClock:
    """Implementación de producción del puerto `Clock`."""

    def now(self) -> datetime:
        return datetime.now(UTC)


def get_session(request: Request) -> Iterator[Session]:
    """Entrega una sesión de la fábrica registrada en la app."""
    session_factory = request.app.state.session_factory
    session: Session = session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_clock() -> Clock:
    """Entrega el reloj del sistema; los tests lo sobrescriben."""
    return SystemClock()


SessionDep = Annotated[Session, Depends(get_session)]
ClockDep = Annotated[Clock, Depends(get_clock)]
