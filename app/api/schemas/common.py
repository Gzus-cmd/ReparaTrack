"""Esquemas compartidos por la API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Respuesta de `GET /api/v1/health`."""

    status: Literal["ok"] = Field(description="Estado general del servicio.")
    database: Literal["ok"] = Field(description="Estado de la base de datos.")


class ErrorDetail(BaseModel):
    """Cuerpo estable del error: código en inglés y mensaje en español."""

    code: str = Field(description="Código estable en inglés (por ejemplo, invalid_transition).")
    message: str = Field(description="Mensaje legible en español neutro para la UI.")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Contexto del error: campo, transición, días, regla, etc.",
    )


class ErrorEnvelope(BaseModel):
    """Envelope uniforme de error del contrato de la API (plan §3)."""

    error: ErrorDetail
