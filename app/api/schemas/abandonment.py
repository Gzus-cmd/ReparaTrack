"""Esquemas del contrato de abandono (RF-10)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AbandonmentCandidateRead(BaseModel):
    """Servicio que ya cumple el umbral de una regla de abandono."""

    service_order_id: int = Field(description="Servicio candidato a marcar ABANDONED.")
    status: str = Field(description="Estado actual: AWAITING_APPROVAL o READY_FOR_PICKUP.")
    days_in_status: int = Field(description="Días calendario en el estado actual.")
    threshold_days: int = Field(description="Umbral de la regla: 30 (RN-10) o 180 (RN-07).")
    rule: str = Field(description="Regla aplicable: RN-10 o RN-07; nunca se mezclan.")
    customer_name: str = Field(description="Cliente del servicio.")
    equipment_internal_code: str = Field(description="Código interno del equipo.")
