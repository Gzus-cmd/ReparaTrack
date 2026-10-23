"""Router de órdenes de servicio: recepción y ficha (RF-04, RF-06 / T-21, T-26)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import (
    ClockDep,
    SessionDep,
    build_service_detail_service,
    build_service_order_service,
)
from app.api.schemas.equipment import CatalogReferenceRead
from app.api.schemas.service_orders import (
    AllowedTransitionsRead,
    CustomerReferenceRead,
    EquipmentReferenceRead,
    ServiceDetailCreate,
    ServiceDetailRead,
    ServiceOrderCreate,
    ServiceOrderPage,
    ServiceOrderRead,
    ServiceOrderUpdate,
    StateHistoryRead,
    TransitionOptionRead,
    TransitionRequest,
)
from app.services.service_detail_service import ServiceDetailView
from app.services.service_order_service import NewEquipment, ServiceOrderView

router = APIRouter(prefix="/service-orders", tags=["servicios"])


def to_read(view: ServiceOrderView) -> ServiceOrderRead:
    """Traduce la vista del servicio al contrato HTTP."""
    return ServiceOrderRead(
        id=view.id,
        equipment=EquipmentReferenceRead(
            id=view.equipment.id,
            internal_code=view.equipment.internal_code,
            model=view.equipment.model,
        ),
        customer=CustomerReferenceRead(
            id=view.customer.id,
            name=view.customer.name,
            phone=view.customer.phone,
        ),
        received_at=view.received_at,
        delivered_at=view.delivered_at,
        reported_failure=view.reported_failure,
        physical_condition=view.physical_condition,
        accessories=view.accessories,
        password_requested=view.password_requested,
        status=view.status,
        status_label=view.status_label,
        days_in_status=view.days_in_status,
        days_since_reception=view.days_since_reception,
        details_count=view.details_count,
        origin_service_id=view.origin_service_id,
        allowed_transitions=[option.to_status for option in view.transitions],
    )


@router.post(
    "",
    response_model=ServiceOrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Recepciona un equipo y abre su servicio en RECEIVED",
)
def create_service_order(
    payload: ServiceOrderCreate, session: SessionDep, clock: ClockDep
) -> ServiceOrderRead:
    """Valida los cinco campos, resuelve el equipo (XOR) y registra el historial."""
    new_equipment = (
        None
        if payload.new_equipment is None
        else NewEquipment(
            device_type_id=payload.new_equipment.device_type_id,
            brand_id=payload.new_equipment.brand_id,
            model=payload.new_equipment.model,
            serial_number=payload.new_equipment.serial_number,
        )
    )
    view = build_service_order_service(session, clock).create(
        customer_id=payload.customer_id,
        equipment_id=payload.equipment_id,
        new_equipment=new_equipment,
        reported_failure=payload.reported_failure,
        accessories=payload.accessories,
        physical_condition=payload.physical_condition,
        password_requested=payload.password_requested,
    )
    return to_read(view)


@router.get(
    "",
    response_model=ServiceOrderPage,
    summary="Bandeja de servicios filtrable por estado, cliente o equipo",
)
def list_service_orders(
    session: SessionDep,
    clock: ClockDep,
    status_filter: str | None = Query(default=None, alias="status"),
    customer_id: int | None = Query(default=None, gt=0),
    equipment_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ServiceOrderPage:
    """Devuelve la página y el total; un estado desconocido responde `422`."""
    page = build_service_order_service(session, clock).list(
        status=status_filter,
        customer_id=customer_id,
        equipment_id=equipment_id,
        limit=limit,
        offset=offset,
    )
    return ServiceOrderPage(
        items=[to_read(item) for item in page.items], total=page.total
    )


@router.get(
    "/{service_order_id}",
    response_model=ServiceOrderRead,
    summary="Ficha del servicio con días y transiciones permitidas",
)
def get_service_order(
    service_order_id: int, session: SessionDep, clock: ClockDep
) -> ServiceOrderRead:
    """Devuelve la ficha completa o `404`."""
    return to_read(build_service_order_service(session, clock).get(service_order_id))


@router.get(
    "/{service_order_id}/transitions",
    response_model=AllowedTransitionsRead,
    summary="Destinos permitidos con sus guardas ya evaluadas",
)
def get_allowed_transitions(
    service_order_id: int, session: SessionDep, clock: ClockDep
) -> AllowedTransitionsRead:
    """Marca `blocked_reason` cuando falta detalle o no se alcanzó el umbral."""
    view = build_service_order_service(session, clock).get(service_order_id)
    return AllowedTransitionsRead(
        current=view.status,
        allowed=[
            TransitionOptionRead(
                to_status=option.to_status,
                status_label=option.status_label,
                blocked_reason=option.blocked_reason,
            )
            for option in view.transitions
        ],
    )


@router.patch(
    "/{service_order_id}",
    response_model=ServiceOrderRead,
    summary="Actualización cerrada: la evidencia de recepción es inmutable",
)
def update_service_order(
    service_order_id: int,
    payload: ServiceOrderUpdate,
    session: SessionDep,
    clock: ClockDep,
) -> ServiceOrderRead:
    """Ningún campo de recepción es editable (RN-08); un envío vacío es un no-op."""
    return to_read(build_service_order_service(session, clock).get(service_order_id))


@router.get(
    "/{service_order_id}/history",
    response_model=list[StateHistoryRead],
    summary="Bitácora inmutable del servicio",
)
def get_service_order_history(
    service_order_id: int, session: SessionDep, clock: ClockDep
) -> list[StateHistoryRead]:
    """Devuelve las filas del historial ordenadas por fecha y hora."""
    entries = build_service_order_service(session, clock).history(service_order_id)
    return [
        StateHistoryRead(
            id=entry.id,
            status=entry.status,
            status_label=entry.status_label,
            changed_at=entry.changed_at,
            comment=entry.comment,
        )
        for entry in entries
    ]


@router.post(
    "/{service_order_id}/transitions",
    response_model=ServiceOrderRead,
    summary="Ejecuta una transición válida y registra su historial",
)
def transition_service_order(
    service_order_id: int,
    payload: TransitionRequest,
    session: SessionDep,
    clock: ClockDep,
) -> ServiceOrderRead:
    """Acepta la transición o la rechaza sin efectos (estado e historial intactos)."""
    view = build_service_order_service(session, clock).transition(
        service_order_id,
        target=payload.to_status,
        comment=payload.comment,
        confirm=payload.confirm,
    )
    return to_read(view)


def _detail_to_read(view: ServiceDetailView) -> ServiceDetailRead:
    return ServiceDetailRead(
        id=view.id,
        service_order_id=view.service_order_id,
        operation_type=CatalogReferenceRead(
            id=view.operation_type.id, name=view.operation_type.name
        ),
        component=(
            None
            if view.component is None
            else CatalogReferenceRead(id=view.component.id, name=view.component.name)
        ),
        description=view.description,
        created_at=view.created_at,
    )


@router.get(
    "/{service_order_id}/details",
    response_model=list[ServiceDetailRead],
    summary="Líneas de detalle registradas en el servicio",
)
def list_service_details(service_order_id: int, session: SessionDep) -> list[ServiceDetailRead]:
    """Devuelve las líneas en orden de carga."""
    views = build_service_detail_service(session).list(service_order_id)
    return [_detail_to_read(view) for view in views]


@router.post(
    "/{service_order_id}/details",
    response_model=ServiceDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registra una operación con componente opcional",
)
def create_service_detail(
    service_order_id: int, payload: ServiceDetailCreate, session: SessionDep
) -> ServiceDetailRead:
    """Rechaza líneas nuevas sobre órdenes terminales con `409`."""
    view = build_service_detail_service(session).add(
        service_order_id,
        operation_type_id=payload.operation_type_id,
        component_id=payload.component_id,
        description=payload.description,
    )
    return _detail_to_read(view)


@router.delete(
    "/{service_order_id}/details/{detail_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Corrige una línea mal cargada",
)
def delete_service_detail(
    service_order_id: int, detail_id: int, session: SessionDep
) -> None:
    """Borra la línea solo si la orden no es terminal."""
    build_service_detail_service(session).delete(service_order_id, detail_id)
