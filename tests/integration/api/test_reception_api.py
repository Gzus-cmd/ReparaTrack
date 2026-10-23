"""T-21 — Recepción de servicios (RF-04 / RN-01, RN-06, RN-08).

Cubre los cinco campos obligatorios, el XOR del equipo, la primera fila de
historial en la misma transacción y la ausencia total de contraseñas.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Equipment, ServiceOrder, StateHistory
from support.factories import (
    SERVICE_ORDERS_URL,
    create_order,
    make_customer,
    new_equipment_payload,
    reception_payload,
    transition,
)

ORDERS = SERVICE_ORDERS_URL


def _count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _post(client, session: Session, **overrides):
    customer = make_customer(session)
    payload = reception_payload(customer.id, **overrides)
    return client.post(ORDERS, json=payload)


def test_reception_creates_the_order_with_its_initial_history_row(client, session: Session) -> None:
    response = _post(client, session, new_equipment=new_equipment_payload(session))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "RECEIVED"
    assert body["status_label"] == "Recibido"
    received_at = datetime.fromisoformat(body["received_at"])
    assert received_at.tzinfo is not None
    assert body["password_requested"] is False
    assert body["details_count"] == 0
    assert _count(session, ServiceOrder) == 1
    entries = session.scalars(select(StateHistory)).all()
    assert len(entries) == 1
    assert entries[0].status.value == "RECEIVED"
    assert entries[0].service_order_id == body["id"]


def test_reception_with_existing_equipment_links_it(client, session: Session) -> None:
    equipment_payload = new_equipment_payload(session)
    created = client.post("/api/v1/equipments", json=equipment_payload)
    equipment_id = created.json()["id"]

    response = _post(client, session, equipment_id=equipment_id)

    assert response.status_code == 201, response.text
    assert response.json()["equipment"]["internal_code"] == "EQ-000001"
    assert _count(session, Equipment) == 1


def test_reception_with_new_equipment_creates_it_in_the_same_transaction(
    client, session: Session
) -> None:
    response = _post(client, session, new_equipment=new_equipment_payload(session, "IdeaPad"))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["equipment"]["internal_code"] == "EQ-000001"
    assert body["equipment"]["model"] == "IdeaPad"
    assert _count(session, Equipment) == 1
    assert session.scalars(select(Equipment)).one().id == body["equipment"]["id"]


@pytest.mark.parametrize("missing", ["reported_failure", "accessories", "physical_condition"])
def test_reception_without_a_required_field_is_rejected_with_its_name(
    client, session: Session, missing: str
) -> None:
    customer = make_customer(session)
    payload = reception_payload(customer.id, new_equipment=new_equipment_payload(session))
    payload.pop(missing)

    response = client.post(ORDERS, json=payload)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["field"] == missing
    assert _count(session, ServiceOrder) == 0
    assert _count(session, Equipment) == 0
    assert _count(session, StateHistory) == 0


def test_reception_with_a_blank_reported_failure_is_rejected(client, session: Session) -> None:
    response = _post(
        client,
        session,
        new_equipment=new_equipment_payload(session),
        reported_failure="   ",
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "reported_failure"
    assert _count(session, ServiceOrder) == 0


def test_reception_with_both_equipment_sources_is_rejected(client, session: Session) -> None:
    equipment = client.post("/api/v1/equipments", json=new_equipment_payload(session)).json()

    response = _post(
        client,
        session,
        equipment_id=equipment["id"],
        new_equipment=new_equipment_payload(session),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "equipment_source_invalid"
    assert _count(session, ServiceOrder) == 0
    assert _count(session, Equipment) == 1


def test_reception_without_any_equipment_source_is_rejected(client, session: Session) -> None:
    customer = make_customer(session)

    response = client.post(ORDERS, json=reception_payload(customer.id))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "equipment_source_invalid"
    assert _count(session, ServiceOrder) == 0


def test_reception_with_unknown_customer_is_rejected(client, session: Session) -> None:
    payload = reception_payload(
        9999, new_equipment={**new_equipment_payload(session), "model": "ThinkPad"}
    )

    response = client.post(ORDERS, json=payload)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["field"] == "customer_id"
    assert _count(session, ServiceOrder) == 0
    assert _count(session, Equipment) == 0


def test_reception_with_unknown_equipment_is_rejected(client, session: Session) -> None:
    response = _post(client, session, equipment_id=9999)

    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "equipment_id"
    assert _count(session, ServiceOrder) == 0


def test_reception_exposes_only_the_password_flag(client, session: Session) -> None:
    response = _post(
        client,
        session,
        new_equipment=new_equipment_payload(session),
        password_requested=True,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["password_requested"] is True
    assert not [key for key in body if "password" in key and key != "password_requested"]


def test_reception_rejects_a_password_value(client, session: Session) -> None:
    customer = make_customer(session)
    payload = reception_payload(
        customer.id,
        new_equipment=new_equipment_payload(session),
        password="secreto",
    )

    response = client.post(ORDERS, json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert _count(session, ServiceOrder) == 0
    assert _count(session, StateHistory) == 0


# --- T-25: la evidencia de recepción es inmutable (RN-08) --------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("physical_condition", "Sin marcas visibles"),
        ("accessories", "Ninguno"),
    ],
)
def test_patch_rejects_an_immutable_reception_field(
    client, session: Session, field: str, value: str
) -> None:
    order = create_order(client, session)

    response = client.patch(f"{ORDERS}/{order['id']}", json={field: value})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "immutable_field"
    assert error["details"]["field"] == field
    current = client.get(f"{ORDERS}/{order['id']}").json()
    assert current[field] == order[field]


# --- T-26: endpoints de lectura (ficha y bandeja) ----------------------------


def test_service_order_read_exposes_metrics_and_allowed_transitions(
    client, session: Session, clock
) -> None:
    order = create_order(client, session)
    clock.travel(days=3)

    response = client.get(f"{ORDERS}/{order['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "RECEIVED"
    assert body["status_label"] == "Recibido"
    assert body["days_in_status"] == 3
    assert body["days_since_reception"] == 3
    assert body["details_count"] == 0
    assert body["allowed_transitions"] == ["DIAGNOSING"]


def test_list_orders_filters_by_status_and_paginates(client, session: Session) -> None:
    first = create_order(client, session)
    second = create_order(client, session)
    transition(client, first["id"], "DIAGNOSING")

    by_status = client.get(f"{ORDERS}?status=DIAGNOSING")
    page = client.get(f"{ORDERS}?limit=1&offset=0")

    assert by_status.status_code == 200
    assert [item["id"] for item in by_status.json()["items"]] == [first["id"]]
    assert by_status.json()["total"] == 1
    assert page.status_code == 200
    assert len(page.json()["items"]) == 1
    assert page.json()["total"] == 2
    assert {first["id"], second["id"]} == {
        item["id"] for item in client.get(ORDERS).json()["items"]
    }


def test_list_orders_filters_by_equipment_and_customer(client, session: Session) -> None:
    first = create_order(client, session)
    second = create_order(client, session)

    by_equipment = client.get(f"{ORDERS}?equipment_id={first['equipment']['id']}")
    by_customer = client.get(f"{ORDERS}?customer_id={second['customer']['id']}")

    assert [item["id"] for item in by_equipment.json()["items"]] == [first["id"]]
    assert [item["id"] for item in by_customer.json()["items"]] == [second["id"]]


def test_list_orders_with_unknown_status_returns_422(client) -> None:
    response = client.get(f"{ORDERS}?status=EN_REPARACION")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_status"


def test_get_unknown_order_returns_404(client) -> None:
    response = client.get(f"{ORDERS}/9999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
