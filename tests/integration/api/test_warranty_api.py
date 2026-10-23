"""T-32 — Garantía y reingreso (RF-09 / RN-04).

El sistema alerta con los candidatos dentro de los 90 días y valida el vínculo
en la misma transacción de la recepción; la decisión de vincular sigue siendo
del técnico y nunca se compara el texto de las fallas.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from support.factories import (
    SERVICE_ORDERS_URL,
    catalog_ids,
    create_order,
    drive_to,
    make_customer,
    new_equipment_payload,
    reception_payload,
)

from app.db.models import Equipment, ServiceOrder

WARRANTY_URL = "/api/v1/warranty"
NOW = datetime(2026, 10, 22, 15, 0, tzinfo=UTC)


def _count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _create_equipment(client, session: Session, model: str = "ThinkPad") -> dict:
    ids = catalog_ids(session)
    response = client.post(
        "/api/v1/equipments",
        json={
            "device_type_id": ids["device_type_id"],
            "brand_id": ids["brand_id"],
            "model": model,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _delivered_order(client, session: Session, equipment_id: int, **overrides) -> dict:
    """Recepciona un equipo existente y lo entrega recorriendo la matriz real."""
    order = create_order(client, session, equipment_id=equipment_id, **overrides)
    return drive_to(client, session, order["id"], "DELIVERED")


def _post_reentry(client, session: Session, equipment_id: int, origin_service_id: int):
    customer = make_customer(session, name="Cliente reingreso", phone="988777666")
    payload = reception_payload(
        customer.id,
        equipment_id=equipment_id,
        origin_service_id=origin_service_id,
    )
    return client.post(SERVICE_ORDERS_URL, json=payload)


def test_candidates_list_a_delivery_inside_the_window(client, session: Session, clock) -> None:
    equipment = _create_equipment(client, session)
    delivered = _delivered_order(client, session, equipment["id"], reported_failure="No carga")
    clock.travel(days=89)

    response = client.get(f"{WARRANTY_URL}/candidates?equipment_id={equipment['id']}")

    assert response.status_code == 200, response.text
    candidates = response.json()
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["service_order_id"] == delivered["id"]
    assert candidate["days_since_delivery"] == 89
    assert candidate["warranty_days_left"] == 1
    assert candidate["reported_failure"] == "No carga"
    assert datetime.fromisoformat(candidate["delivered_at"]) == datetime.fromisoformat(
        delivered["delivered_at"]
    )


@pytest.mark.parametrize("days", [90, 91])
def test_candidates_are_empty_outside_the_window(client, session: Session, clock, days) -> None:
    equipment = _create_equipment(client, session)
    _delivered_order(client, session, equipment["id"])
    clock.travel(days=days)

    response = client.get(f"{WARRANTY_URL}/candidates?equipment_id={equipment['id']}")

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_candidates_respect_the_explicit_as_of(client, session: Session) -> None:
    equipment = _create_equipment(client, session)
    _delivered_order(client, session, equipment["id"])
    as_of = (NOW + timedelta(days=91)).isoformat()

    response = client.get(
        f"{WARRANTY_URL}/candidates",
        params={"equipment_id": equipment["id"], "as_of": as_of},
    )

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_reentry_linked_inside_the_window_is_created(client, session: Session, clock) -> None:
    equipment = _create_equipment(client, session)
    origin = _delivered_order(client, session, equipment["id"], reported_failure="No carga")
    clock.travel(days=89)

    response = _post_reentry(client, session, equipment["id"], origin["id"])

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["origin_service_id"] == origin["id"]
    assert body["status"] == "RECEIVED"
    assert _count(session, ServiceOrder) == 2

    history = client.get(f"/api/v1/equipments/{equipment['id']}/history").json()
    services = history["services"]
    assert len(services) == 2
    assert {service["id"] for service in services} == {origin["id"], body["id"]}
    linked = [service for service in services if service["origin_service_id"] == origin["id"]]
    assert [service["id"] for service in linked] == [body["id"]]


@pytest.mark.parametrize("days", [90, 91])
def test_reentry_after_ninety_days_is_rejected(client, session: Session, clock, days) -> None:
    equipment = _create_equipment(client, session)
    origin = _delivered_order(client, session, equipment["id"])
    clock.travel(days=days)
    before = _count(session, ServiceOrder)

    response = _post_reentry(client, session, equipment["id"], origin["id"])

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "warranty_expired"
    assert error["details"]["origin_service_id"] == origin["id"]
    assert error["details"]["days_since_delivery"] == days
    assert error["details"]["warranty_days"] == 90
    assert _count(session, ServiceOrder) == before


def test_origin_from_another_equipment_is_rejected(client, session: Session, clock) -> None:
    origin_equipment = _create_equipment(client, session, "ThinkPad")
    other_equipment = _create_equipment(client, session, "IdeaPad")
    origin = _delivered_order(client, session, origin_equipment["id"])
    clock.travel(days=10)
    before = _count(session, ServiceOrder)

    response = _post_reentry(client, session, other_equipment["id"], origin["id"])

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "warranty_equipment_mismatch"
    assert error["details"]["origin_service_id"] == origin["id"]
    assert error["details"]["origin_equipment_id"] == origin_equipment["id"]
    assert error["details"]["equipment_id"] == other_equipment["id"]
    assert _count(session, ServiceOrder) == before


def test_origin_not_delivered_is_rejected(client, session: Session, clock) -> None:
    equipment = _create_equipment(client, session)
    origin = create_order(client, session, equipment_id=equipment["id"])
    clock.travel(days=10)
    before = _count(session, ServiceOrder)

    response = _post_reentry(client, session, equipment["id"], origin["id"])

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "origin_not_delivered"
    assert error["details"]["origin_service_id"] == origin["id"]
    assert error["details"]["status"] == "RECEIVED"
    assert _count(session, ServiceOrder) == before


def test_second_reentry_to_the_same_origin_is_rejected(client, session: Session, clock) -> None:
    equipment = _create_equipment(client, session)
    origin = _delivered_order(client, session, equipment["id"])
    clock.travel(days=30)
    first = _post_reentry(client, session, equipment["id"], origin["id"])
    assert first.status_code == 201, first.text
    before = _count(session, ServiceOrder)

    second = _post_reentry(client, session, equipment["id"], origin["id"])

    assert second.status_code == 409
    error = second.json()["error"]
    assert error["code"] == "origin_already_linked"
    assert error["details"]["origin_service_id"] == origin["id"]
    assert error["details"]["linked_service_id"] == first.json()["id"]
    assert _count(session, ServiceOrder) == before


@pytest.mark.parametrize(
    ("days", "eligible", "reason"), [(89, True, "within_warranty"), (90, False, "warranty_expired")]
)
def test_eligibility_endpoint_reports_the_window(
    client, session: Session, clock, days, eligible, reason
) -> None:
    equipment = _create_equipment(client, session)
    origin = _delivered_order(client, session, equipment["id"])
    clock.travel(days=days)

    response = client.get(f"{WARRANTY_URL}/eligibility?origin_service_id={origin['id']}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["eligible"] is eligible
    assert body["days_since_delivery"] == days
    assert body["reason"] == reason


def test_unknown_origin_returns_404(client) -> None:
    response = client.get(f"{WARRANTY_URL}/eligibility?origin_service_id=9999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_reception_with_unknown_origin_returns_404(client, session: Session) -> None:
    equipment = _create_equipment(client, session)
    customer = make_customer(session, name="Cliente sin origen", phone="966555444")
    payload = reception_payload(customer.id, equipment_id=equipment["id"], origin_service_id=9999)

    response = client.post(SERVICE_ORDERS_URL, json=payload)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert _count(session, ServiceOrder) == 0


def test_new_equipment_cannot_link_to_an_existing_origin(client, session: Session, clock) -> None:
    equipment = _create_equipment(client, session)
    origin = _delivered_order(client, session, equipment["id"])
    clock.travel(days=10)
    customer = make_customer(session, name="Cliente equipo nuevo", phone="955444333")
    payload = reception_payload(
        customer.id,
        new_equipment=new_equipment_payload(session, "IdeaPad"),
        origin_service_id=origin["id"],
    )

    response = client.post(SERVICE_ORDERS_URL, json=payload)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "warranty_equipment_mismatch"
    assert error["details"]["origin_equipment_id"] == equipment["id"]
    assert error["details"]["equipment_id"] is None
    # La validación corre antes de crear el equipo nuevo: nada queda escrito.
    assert _count(session, Equipment) == 1
    assert _count(session, ServiceOrder) == 1
