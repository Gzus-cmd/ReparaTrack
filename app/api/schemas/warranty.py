"""Esquemas del contrato de garantía (RF-09)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WarrantyCandidateRead(BaseModel):
    """Servicio entregado dentro de la garantía de 90 días."""

    service_order_id: int = Field(description="Servicio entregado que se puede vincular.")
    delivered_at: datetime = Field(description="Fecha y hora de entrega del servicio original.")
    days_since_delivery: int = Field(description="Días calendario transcurridos desde la entrega.")
    warranty_days_left: int = Field(description="Días de garantía restantes.")
    reported_failure: str = Field(description="Falla reportada en el servicio original.")


class WarrantyEligibilityRead(BaseModel):
    """Evaluación de un servicio de origen concreto."""

    eligible: bool = Field(description="Verdadero si el origen todavía está en garantía.")
    days_since_delivery: int | None = Field(
        description="Días desde la entrega; nulo cuando el origen no fue entregado."
    )
    reason: str = Field(
        description="Motivo estable: within_warranty, warranty_expired u origin_not_delivered."
    )
