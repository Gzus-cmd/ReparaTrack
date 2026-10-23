"""Esquemas del tablero de equipos en taller (RF-07)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WorkbenchItemRead(BaseModel):
    """Fila del tablero: cliente, equipo, estado y días transcurridos."""

    service_order_id: int
    customer_name: str
    equipment_internal_code: str
    device_type: str
    status: str
    status_label: str
    received_at: datetime
    days_since_reception: int
    days_in_status: int
    is_over_threshold: bool = Field(
        description="Verdadero cuando la regla de abandono del estado ya se cumple."
    )
    threshold_rule: str | None = Field(
        description="Regla de abandono aplicable al estado: RN-07, RN-10 o nulo."
    )


class WorkbenchRead(BaseModel):
    """Listado de equipos en taller ordenado por días transcurridos."""

    items: list[WorkbenchItemRead] = Field(
        description="Órdenes sin entregar, de la más antigua a la más reciente."
    )


class AlertGroupRead(BaseModel):
    """Servicios que ya cumplen una regla de abandono (RN-07 o RN-10)."""

    rule: str
    threshold_days: int
    count: int
    service_order_ids: list[int]


class DashboardSummaryRead(BaseModel):
    """Conteo por estado y alertas de umbral separadas por regla."""

    by_status: dict[str, int] = Field(
        description="Conteo por estado: siempre las diez claves, con cero si no hay casos."
    )
    alerts: dict[str, AlertGroupRead] = Field(
        description="Grupos excluyentes RN-07 y RN-10, nunca mezclados."
    )
