"""Router de equipos: alta con correlativo y búsqueda (RF-03 / T-19, T-20)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import SessionDep, build_equipment_service
from app.api.schemas.equipment import (
    CatalogReferenceRead,
    CustomerReferenceRead,
    EquipmentCreate,
    EquipmentRead,
)
from app.services.equipment_service import CustomerReference, EquipmentView

router = APIRouter(prefix="/equipments", tags=["equipos"])


def _to_read(view: EquipmentView) -> EquipmentRead:
    owner = view.current_owner
    return EquipmentRead(
        id=view.id,
        internal_code=view.internal_code,
        device_type=CatalogReferenceRead(id=view.device_type.id, name=view.device_type.name),
        brand=CatalogReferenceRead(id=view.brand.id, name=view.brand.name),
        model=view.model,
        serial_number=view.serial_number,
        created_at=view.created_at,
        current_owner=None if owner is None else _to_customer_read(owner),
        previous_services_count=view.previous_services_count,
    )


def _to_customer_read(owner: CustomerReference) -> CustomerReferenceRead:
    return CustomerReferenceRead(id=owner.id, name=owner.name, phone=owner.phone)


@router.get(
    "/lookup",
    response_model=EquipmentRead,
    summary="Identifica un equipo por código interno o número de serie",
)
def lookup_equipment(
    session: SessionDep,
    internal_code: str | None = Query(default=None, description="Código interno (precedente)."),
    serial_number: str | None = Query(default=None, description="Número de serie opcional."),
) -> EquipmentRead:
    """Devuelve el equipo con su historial anticipado; el código manda (D-06)."""
    view = build_equipment_service(session).lookup(
        internal_code=internal_code, serial_number=serial_number
    )
    return _to_read(view)


@router.post(
    "",
    response_model=EquipmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registra un equipo y genera su código interno",
)
def create_equipment(payload: EquipmentCreate, session: SessionDep) -> EquipmentRead:
    """Genera el correlativo `EQ-XXXXXX` y valida que los maestros estén activos."""
    view = build_equipment_service(session).create(
        device_type_id=payload.device_type_id,
        brand_id=payload.brand_id,
        model=payload.model,
        serial_number=payload.serial_number,
    )
    return _to_read(view)
