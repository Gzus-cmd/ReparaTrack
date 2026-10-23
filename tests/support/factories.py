"""Constructores explícitos para las pruebas de recepción, detalle y transiciones.

Regla del plan §4.4: el atajo nunca miente. Para ubicar una orden en un estado
se ejecutan las transiciones reales por HTTP; nunca se escribe el estado a mano.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Brand, Customer, DeviceType, OperationType
from app.db.seed import seed_catalogs

SERVICE_ORDERS_URL = "/api/v1/service-orders"

#: Camino de transiciones reales desde `RECEIVED` hasta cada estado alcanzable.
TRANSITION_PATHS: dict[str, list[str]] = {
    "DIAGNOSING": ["DIAGNOSING"],
    "AWAITING_APPROVAL": ["DIAGNOSING", "AWAITING_APPROVAL"],
    "AWAITING_PART": ["DIAGNOSING", "AWAITING_PART"],
    "IN_REPAIR": ["DIAGNOSING", "AWAITING_APPROVAL", "IN_REPAIR"],
    "NOT_REPARABLE": ["DIAGNOSING", "NOT_REPARABLE"],
    "REJECTED": ["DIAGNOSING", "AWAITING_APPROVAL", "REJECTED"],
    "READY_FOR_PICKUP": [
        "DIAGNOSING",
        "AWAITING_APPROVAL",
        "IN_REPAIR",
        "ADD_DETAIL",
        "READY_FOR_PICKUP",
    ],
    "DELIVERED": [
        "DIAGNOSING",
        "AWAITING_APPROVAL",
        "IN_REPAIR",
        "ADD_DETAIL",
        "READY_FOR_PICKUP",
        "DELIVERED",
    ],
}


def catalog_ids(session: Session) -> dict[str, int]:
    """Siembra los maestros y devuelve los identificadores que usan los tests."""
    seed_catalogs(session)
    device_type = session.scalars(select(DeviceType).where(DeviceType.name == "Laptop")).one()
    brand = session.scalars(select(Brand).where(Brand.name == "HP")).one()
    operation = session.scalars(
        select(OperationType).where(OperationType.name == "Diagnóstico")
    ).one()
    return {
        "device_type_id": device_type.id,
        "brand_id": brand.id,
        "operation_type_id": operation.id,
    }


def make_customer(session: Session, name: str = "Ana Pérez", phone: str = "999111222") -> Customer:
    """Cliente persistido con contacto mínimo."""
    customer = Customer(name=name, phone=phone)
    session.add(customer)
    session.flush()
    return customer


def reception_payload(customer_id: int, **overrides: Any) -> dict[str, Any]:
    """Cuerpo de recepción completo; cada test decide la fuente del equipo."""
    payload: dict[str, Any] = {
        "customer_id": customer_id,
        "reported_failure": "No enciende",
        "accessories": "Cargador",
        "physical_condition": "Golpe leve en la tapa",
    }
    payload.update(overrides)
    return payload


def new_equipment_payload(session: Session, model: str = "ThinkPad") -> dict[str, Any]:
    """Datos de un equipo nuevo para la recepción (XOR con `equipment_id`)."""
    ids = catalog_ids(session)
    return {
        "device_type_id": ids["device_type_id"],
        "brand_id": ids["brand_id"],
        "model": model,
    }


def create_order(
    client,
    session: Session,
    *,
    equipment_id: int | None = None,
    new_equipment: dict[str, Any] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Recepciona una orden por HTTP y devuelve su representación."""
    customer = make_customer(session, name=f"Cliente {len(overrides)}", phone="999000111")
    if equipment_id is None and new_equipment is None:
        new_equipment = new_equipment_payload(session)
    payload = reception_payload(customer.id, **overrides)
    if equipment_id is not None:
        payload["equipment_id"] = equipment_id
    if new_equipment is not None:
        payload["new_equipment"] = new_equipment
    response = client.post(SERVICE_ORDERS_URL, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def transition(client, order_id: int, to_status: str, **body: Any):
    """Ejecuta una transición por HTTP y devuelve la respuesta."""
    payload: dict[str, Any] = {"to_status": to_status}
    payload.update(body)
    return client.post(f"{SERVICE_ORDERS_URL}/{order_id}/transitions", json=payload)


def add_diagnostic_detail(client, session: Session, order_id: int) -> dict[str, Any]:
    """Registra la línea de "Diagnóstico" que satisface RN-03."""
    ids = catalog_ids(session)
    response = client.post(
        f"{SERVICE_ORDERS_URL}/{order_id}/details",
        json={
            "operation_type_id": ids["operation_type_id"],
            "description": "Diagnóstico de placa",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def drive_to(client, session: Session, order_id: int, target: str) -> dict[str, Any]:
    """Lleva la orden al estado pedido recorriendo solo transiciones válidas."""
    for step in TRANSITION_PATHS[target]:
        if step == "ADD_DETAIL":
            add_diagnostic_detail(client, session, order_id)
            continue
        response = transition(client, order_id, step)
        assert response.status_code == 200, response.text
    return response.json()
