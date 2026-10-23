"""Esquemas compartidos por la API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Respuesta de `GET /api/v1/health`."""

    status: Literal["ok"] = Field(description="Estado general del servicio.")
    database: Literal["ok"] = Field(description="Estado de la base de datos.")
