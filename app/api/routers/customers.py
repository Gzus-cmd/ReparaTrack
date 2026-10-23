"""Router de clientes (RF-02 / T-18)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import SessionDep, build_customer_service
from app.api.schemas.customers import (
    CustomerCreate,
    CustomerPage,
    CustomerRead,
    CustomerUpdate,
    ServiceOrderSummaryRead,
)
from app.services.customer_service import ServiceOrderSummary
from app.services.ports import CustomerRecord

router = APIRouter(prefix="/customers", tags=["clientes"])

CUSTOMER_PATH = "/{customer_id}"


def _to_read(record: CustomerRecord) -> CustomerRead:
    return CustomerRead(
        id=record.id,
        name=record.name,
        phone=record.phone,
        email=record.email,
        document=record.document,
        created_at=record.created_at,
    )


@router.get("", response_model=CustomerPage, summary="Busca clientes")
def list_customers(
    session: SessionDep,
    q: str = Query("", description="Texto a buscar en nombre, teléfono o documento."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> CustomerPage:
    """Devuelve la página de coincidencias y el total encontrado."""
    page = build_customer_service(session).search(q, limit=limit, offset=offset)
    return CustomerPage(items=[_to_read(item) for item in page.items], total=page.total)


@router.get(CUSTOMER_PATH, response_model=CustomerRead, summary="Ficha del cliente")
def get_customer(customer_id: int, session: SessionDep) -> CustomerRead:
    """Devuelve el cliente o `404`."""
    return _to_read(build_customer_service(session).get(customer_id))


@router.post(
    "",
    response_model=CustomerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registra un cliente con su contacto",
)
def create_customer(payload: CustomerCreate, session: SessionDep) -> CustomerRead:
    """Rechaza un documento ya registrado con `409 document_duplicate`."""
    record = build_customer_service(session).create(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        document=payload.document,
    )
    return _to_read(record)


@router.patch(CUSTOMER_PATH, response_model=CustomerRead, summary="Actualiza el contacto")
def update_customer(customer_id: int, payload: CustomerUpdate, session: SessionDep) -> CustomerRead:
    """Actualiza solo los campos enviados del contacto."""
    changes = payload.model_dump(exclude_unset=True)
    return _to_read(build_customer_service(session).update(customer_id, changes))


@router.get(
    "/{customer_id}/history",
    response_model=list[ServiceOrderSummaryRead],
    summary="Servicios del cliente con filtro por rango de recepción",
)
def get_customer_history(
    customer_id: int,
    session: SessionDep,
    received_from: Annotated[
        datetime | None, Query(alias="from", description="Fecha de recepción mínima (inclusiva).")
    ] = None,
    received_to: Annotated[
        datetime | None, Query(alias="to", description="Fecha de recepción máxima (inclusiva).")
    ] = None,
) -> list[ServiceOrderSummaryRead]:
    """Devuelve los servicios del cliente, del más reciente al más antiguo."""
    items = build_customer_service(session).history(
        customer_id, received_from=received_from, received_to=received_to
    )
    return [_summary_to_read(item) for item in items]


def _summary_to_read(item: ServiceOrderSummary) -> ServiceOrderSummaryRead:
    return ServiceOrderSummaryRead(
        id=item.id,
        equipment_internal_code=item.equipment_internal_code,
        received_at=item.received_at,
        delivered_at=item.delivered_at,
        status=item.status,
        status_label=item.status_label,
        reported_failure=item.reported_failure,
        origin_service_id=item.origin_service_id,
    )
