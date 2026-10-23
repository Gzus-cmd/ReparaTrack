"""Agregador de routers de la API v1."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.routers import (
    abandonment,
    catalogs,
    customers,
    dashboard,
    equipments,
    health,
    service_orders,
    warranty,
)
from app.api.schemas.common import ErrorEnvelope

#: Envelope de error uniforme documentado en cada endpoint (plan §3).
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope, "description": "Recurso inexistente."},
    409: {"model": ErrorEnvelope, "description": "Conflicto de negocio o de estado."},
    422: {"model": ErrorEnvelope, "description": "Datos de entrada inválidos."},
}

api_router = APIRouter()
for _router in (
    health.router,
    catalogs.router,
    customers.router,
    equipments.router,
    service_orders.router,
    dashboard.router,
    warranty.router,
    abandonment.router,
):
    api_router.include_router(_router, responses=ERROR_RESPONSES)
