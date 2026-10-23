"""T-24 — Líneas de detalle del servicio (RF-05 / RN-03).

Alta con componente opcional, baja de corrección y bloqueo en órdenes
terminales; incluye el flujo de rechazo cerrado con una línea de "Diagnóstico".
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from support.factories import (
    SERVICE_ORDERS_URL,
    add_diagnostic_detail,
    catalog_ids,
    create_order,
    drive_to,
    transition,
)

from app.db.models import Component

ORDERS = SERVICE_ORDERS_URL


def _ram_id(session: Session) -> int:
    return session.scalars(select(Component).where(Component.name == "RAM")).one().id


def _add(client, order_id: int, **body):
    return client.post(f"{ORDERS}/{order_id}/details", json=body)


def _details(client, order_id: int) -> list[dict]:
    response = client.get(f"{ORDERS}/{order_id}/details")
    assert response.status_code == 200, response.text
    return response.json()


def _count(client, order_id: int) -> int:
    return client.get(f"{ORDERS}/{order_id}").json()["details_count"]


def test_add_detail_with_component(client, session) -> None:
    order = create_order(client, session)
    ids = catalog_ids(session)

    response = _add(
        client,
        order["id"],
        operation_type_id=ids["operation_type_id"],
        component_id=_ram_id(session),
        description="Cambio de módulo RAM",
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["service_order_id"] == order["id"]
    assert body["operation_type"] == {"id": ids["operation_type_id"], "name": "Diagnóstico"}
    assert body["component"] == {"id": _ram_id(session), "name": "RAM"}
    assert body["description"] == "Cambio de módulo RAM"
    assert _count(client, order["id"]) == 1


def test_add_detail_without_component(client, session) -> None:
    order = create_order(client, session)
    ids = catalog_ids(session)

    response = _add(
        client,
        order["id"],
        operation_type_id=ids["operation_type_id"],
        description="Formateo e instalación de sistema",
    )

    assert response.status_code == 201
    assert response.json()["component"] is None
    assert _count(client, order["id"]) == 1


def test_add_detail_to_a_terminal_order_is_rejected(client, session) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "DELIVERED")
    ids = catalog_ids(session)
    before = _details(client, order["id"])

    response = _add(
        client,
        order["id"],
        operation_type_id=ids["operation_type_id"],
        description="Línea tardía",
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "service_order_terminal"
    assert _details(client, order["id"]) == before


def test_delete_detail_in_a_non_terminal_order(client, session) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "IN_REPAIR")
    detail = add_diagnostic_detail(client, session, order["id"])

    response = client.delete(f"{ORDERS}/{order['id']}/details/{detail['id']}")

    assert response.status_code == 204
    assert _details(client, order["id"]) == []
    assert _count(client, order["id"]) == 0


def test_delete_detail_in_a_terminal_order_is_rejected(client, session) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "DELIVERED")
    detail = _details(client, order["id"])[0]

    response = client.delete(f"{ORDERS}/{order['id']}/details/{detail['id']}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "service_order_terminal"
    assert [item["id"] for item in _details(client, order["id"])] == [detail["id"]]


def test_delete_unknown_detail_returns_404(client, session) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "IN_REPAIR")

    response = client.delete(f"{ORDERS}/{order['id']}/details/9999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_details_of_unknown_order_returns_404(client) -> None:
    response = client.get(f"{ORDERS}/9999/details")

    assert response.status_code == 404


def test_add_detail_with_unknown_operation_type_is_rejected(client, session) -> None:
    order = create_order(client, session)

    response = _add(client, order["id"], operation_type_id=9999, description="Cambio")

    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "operation_type_id"
    assert _count(client, order["id"]) == 0


def test_add_detail_with_unknown_component_is_rejected(client, session) -> None:
    order = create_order(client, session)
    ids = catalog_ids(session)

    response = _add(
        client,
        order["id"],
        operation_type_id=ids["operation_type_id"],
        component_id=9999,
        description="Cambio",
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "component_id"
    assert _count(client, order["id"]) == 0


def test_add_detail_with_blank_description_is_rejected(client, session) -> None:
    order = create_order(client, session)
    ids = catalog_ids(session)

    response = _add(
        client, order["id"], operation_type_id=ids["operation_type_id"], description="   "
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "description"


def test_rejection_flow_closes_with_a_real_diagnostic_detail(client, session) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "AWAITING_APPROVAL")
    detail = add_diagnostic_detail(client, session, order["id"])

    rejected = transition(client, order["id"], "REJECTED", comment="Cliente no aprueba")
    delivered = transition(client, order["id"], "DELIVERED")

    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "REJECTED"
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["status"] == "DELIVERED"
    assert delivered.json()["delivered_at"] is not None
    assert _details(client, order["id"]) == [detail]
