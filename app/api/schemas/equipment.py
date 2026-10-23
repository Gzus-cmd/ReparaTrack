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
