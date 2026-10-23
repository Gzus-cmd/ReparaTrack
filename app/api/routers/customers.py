"""Router de clientes (RF-02 / T-18)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import SessionDep, build_customer_service
from app.api.schemas.customers import (
    CustomerCreate,
    CustomerPage,
    CustomerRead,
    CustomerUpdate,
)
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
