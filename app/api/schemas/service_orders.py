"""Esquemas de órdenes de servicio: recepción, lectura y transiciones (RF-04, RF-06)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.schemas.equipment import CatalogReferenceRead
from app.domain.errors import ImmutableFieldError


class NewEquipmentCreate(BaseModel):
    """Equipo que se crea dentro de la transacción de recepción."""

    model_config = ConfigDict(extra="forbid")

    device_type_id: int = Field(gt=0, description="Tipo de dispositivo (maestro activo).")
    brand_id: int = Field(gt=0, description="Marca (maestro activo).")
    model: str = Field(min_length=1, max_length=120, description="Modelo del equipo.")
    serial_number: str | None = Field(
        default=None, max_length=120, description="Número de serie opcional."
    )


class ServiceOrderCreate(BaseModel):
    """Cuerpo de recepción: cinco campos obligatorios y un único origen de equipo."""

    model_config = ConfigDict(extra="forbid")

    customer_id: int = Field(gt=0, description="Cliente existente.")
    equipment_id: int | None = Field(
        default=None, gt=0, description="Equipo existente (XOR con `new_equipment`)."
    )
    new_equipment: NewEquipmentCreate | None = Field(
        default=None, description="Datos de un equipo nuevo (XOR con `equipment_id`)."
    )
    reported_failure: str = Field(
        min_length=1, max_length=500, description="Falla reportada por el cliente."
    )
    accessories: str = Field(min_length=1, max_length=500, description="Accesorios recibidos.")
    physical_condition: str = Field(
        min_length=1, max_length=500, description="Condición física; nunca se edita."
    )
    password_requested: bool = Field(
        default=False, description="Solo el indicador: nunca se almacena la contraseña."
    )
    origin_service_id: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Servicio entregado al que se vincula el reingreso (RF-09). "
            "El sistema alerta; el técnico decide (RN-04)."
        ),
    )


class EquipmentReferenceRead(BaseModel):
    """Referencia mínima al equipo de la orden."""

    id: int
    internal_code: str
    model: str


class CustomerReferenceRead(BaseModel):
    """Contacto mínimo del cliente de la orden."""

    id: int
    name: str
    phone: str


class ServiceOrderRead(BaseModel):
    """Ficha completa de la orden con sus métricas y destinos de la matriz."""

    id: int
    equipment: EquipmentReferenceRead
    customer: CustomerReferenceRead
    received_at: datetime
    delivered_at: datetime | None
    reported_failure: str
    physical_condition: str
    accessories: str
    password_requested: bool
    status: str
    status_label: str
    days_in_status: int
    days_since_reception: int
    details_count: int
    origin_service_id: int | None
    allowed_transitions: list[str]


class ServiceOrderUpdate(BaseModel):
    """Actualización cerrada: la evidencia de recepción no se edita (RN-08)."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _reject_any_field(cls, data: object) -> object:
        """Ningún campo de la recepción es editable: rechaza el primero enviado."""
        if isinstance(data, dict):
            for field, value in data.items():
                raise ImmutableFieldError(field=field, previous=None, new=value)
        return data


class TransitionRequest(BaseModel):
    """Cuerpo de una transición: destino, comentario opcional y confirmación."""

    model_config = ConfigDict(extra="forbid")

    to_status: str = Field(min_length=1, max_length=24, description="Estado destino.")
    comment: str | None = Field(
        default=None, max_length=500, description="Motivo u observación opcional."
    )
    confirm: bool = Field(default=False, description="Confirmación explícita para marcar abandono.")


class StateHistoryRead(BaseModel):
    """Fila de la bitácora inmutable con su etiqueta en español."""

    id: int
    status: str
    status_label: str
    changed_at: datetime
    comment: str | None


class TransitionOptionRead(BaseModel):
    """Destino alcanzable y, si corresponde, el motivo que lo bloquea."""

    to_status: str
    status_label: str
    blocked_reason: str | None


class AllowedTransitionsRead(BaseModel):
    """Estado actual y destinos con sus guardas ya evaluadas."""

    current: str
    allowed: list[TransitionOptionRead]


class ServiceOrderPage(BaseModel):
    """Página de la bandeja con el total de coincidencias."""

    items: list[ServiceOrderRead]
    total: int


class ServiceDetailCreate(BaseModel):
    """Alta de una línea de trabajo con componente opcional."""

    model_config = ConfigDict(extra="forbid")

    operation_type_id: int = Field(gt=0, description="Operación realizada (maestro activo).")
    component_id: int | None = Field(
        default=None, gt=0, description="Componente opcional (maestro activo)."
    )
    description: str = Field(
        min_length=1, max_length=500, description="Detalle del trabajo realizado."
    )


class ServiceDetailRead(BaseModel):
    """Línea de detalle con sus referencias resueltas."""

    id: int
    service_order_id: int
    operation_type: CatalogReferenceRead
    component: CatalogReferenceRead | None
    description: str
    created_at: datetime
