"""Router de equipos: alta con correlativo y búsqueda (RF-03 / T-19, T-20)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import SessionDep, build_equipment_service
from app.api.schemas.equipment import (
    CatalogReferenceRead,
    CustomerReferenceRead,
    EquipmentCreate,
    EquipmentHistoryRead,
    EquipmentRead,
    HistoryDetailRead,
    HistoryServiceRead,
    HistoryStateRead,
)
from app.services.equipment_service import (
    CustomerReference,
    EquipmentHistory,
    EquipmentView,
    HistoryService,
)

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


def _history_service_to_read(service: HistoryService) -> HistoryServiceRead:
    return HistoryServiceRead(
        id=service.id,
        customer=_to_customer_read(service.customer),
        status=service.status,
        status_label=service.status_label,
        received_at=service.received_at,
        delivered_at=service.delivered_at,
        reported_failure=service.reported_failure,
        physical_condition=service.physical_condition,
        accessories=service.accessories,
        password_requested=service.password_requested,
        origin_service_id=service.origin_service_id,
        states=(
            None
            if service.states is None
            else [
                HistoryStateRead(
                    id=state.id,
                    status=state.status,
                    status_label=state.status_label,
                    changed_at=state.changed_at,
                    comment=state.comment,
                )
                for state in service.states
            ]
        ),
        details=(
            None
            if service.details is None
            else [
                HistoryDetailRead(
                    id=detail.id,
                    operation_type=CatalogReferenceRead(
                        id=detail.operation_type.id, name=detail.operation_type.name
                    ),
                    component=(
                        None
                        if detail.component is None
                        else CatalogReferenceRead(
                            id=detail.component.id, name=detail.component.name
                        )
                    ),
                    description=detail.description,
                    created_at=detail.created_at,
                )
                for detail in service.details
            ]
        ),
    )


def _history_to_read(view: EquipmentHistory) -> EquipmentHistoryRead:
    return EquipmentHistoryRead(
        equipment=_to_read(view.equipment),
        services=[_history_service_to_read(service) for service in view.services],
    )


@router.get(
    "/{equipment_ref}/history",
    response_model=EquipmentHistoryRead,
    summary="Historial técnico completo del equipo (id, código interno o serial)",
)
def get_equipment_history(
    equipment_ref: str,
    session: SessionDep,
    include: str | None = Query(
        default=None,
        description="Secciones a incluir, separadas por coma: details, states.",
    ),
) -> EquipmentHistoryRead:
    """Devuelve servicios, estados y detalles; el código manda sobre el serial (D-06)."""
    sections = None if include is None else include.split(",")
    view = build_equipment_service(session).history(equipment_ref, include=sections)
    return _history_to_read(view)


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


@router.get(
    "",
    response_model=list[EquipmentRead],
    summary="Lista los equipos registrados",
)
def list_equipments(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[EquipmentRead]:
    """Devuelve los equipos ordenados del más reciente al más antiguo."""
    views = build_equipment_service(session).list_all(limit=limit, offset=offset)
    return [_to_read(view) for view in views]


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
