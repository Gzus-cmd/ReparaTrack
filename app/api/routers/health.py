"""Router de salud: primer corte vertical observable (T-10)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import SessionDep
from app.api.schemas.common import HealthResponse

router = APIRouter(tags=["salud"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Estado del servicio y de la base de datos",
)
def health(session: SessionDep) -> HealthResponse:
    """Comprueba que la aplicación responde y que la base está accesible."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:  # pragma: no cover - defensa ante BD caída
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "database": "error"},
        ) from exc
    return HealthResponse(status="ok", database="ok")
