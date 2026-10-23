"""Esquemas de equipos (RF-03)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CatalogReferenceRead(BaseModel):
    """Referencia mínima a un maestro en la respuesta de un equipo."""

    id: int
    name: str


class CustomerReferenceRead(BaseModel):
    """Contacto mínimo del dueño vigente del equipo."""

    id: int
    name: str
    phone: str


class EquipmentCreate(BaseModel):
    """Alta de equipo con maestros activos y serial opcional."""

    model_config = ConfigDict(extra="forbid")

    device_type_id: int = Field(gt=0, description="Tipo de dispositivo (maestro activo).")
    brand_id: int = Field(gt=0, description="Marca (maestro activo).")
    model: str = Field(min_length=1, max_length=120, description="Modelo del equipo.")
    serial_number: str | None = Field(
        default=None, max_length=120, description="Número de serie opcional."
    )


class EquipmentRead(BaseModel):
    """Equipo con código interno, referencias e historial anticipado."""

    id: int
    internal_code: str
    device_type: CatalogReferenceRead
    brand: CatalogReferenceRead
    model: str
    serial_number: str | None
    created_at: datetime
    current_owner: CustomerReferenceRead | None
    previous_services_count: int


class HistoryDetailRead(BaseModel):
    """Línea de detalle dentro del historial técnico."""

    id: int
    operation_type: CatalogReferenceRead
    component: CatalogReferenceRead | None
    description: str
    created_at: datetime


class HistoryStateRead(BaseModel):
    """Movimiento de la bitácora dentro del historial técnico."""

    id: int
    status: str
    status_label: str
    changed_at: datetime
    comment: str | None


class HistoryServiceRead(BaseModel):
    """Servicio previo del equipo con su cliente y las secciones pedidas."""

    id: int
    customer: CustomerReferenceRead
    status: str
    status_label: str
    received_at: datetime
    delivered_at: datetime | None
    reported_failure: str
    physical_condition: str
    accessories: str
    password_requested: bool
    origin_service_id: int | None
    states: list[HistoryStateRead] | None = Field(
        description="Bitácora del servicio; `null` cuando la sección no se pidió."
    )
    details: list[HistoryDetailRead] | None = Field(
        description="Líneas de trabajo; `null` cuando la sección no se pidió."
    )


class EquipmentHistoryRead(BaseModel):
    """Historial técnico completo del equipo (RF-08)."""

    equipment: EquipmentRead
    services: list[HistoryServiceRead] = Field(
        description="Servicios del equipo, del más reciente al más antiguo."
    )
