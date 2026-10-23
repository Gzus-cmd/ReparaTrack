"""T-27 — UI de recepción y ficha del servicio (RF-04, RF-06).

Las vistas consumen los mismos servicios que la API y funcionan sin JavaScript:
formularios HTML nativos con mensajes en español neutro.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from support.factories import (
    add_diagnostic_detail,
    catalog_ids,
    create_order,
    make_customer,
    transition,
)


def test_reception_page_shows_the_five_required_fields(client) -> None:
    response = client.get("/reception")

    assert response.status_code == 200
    body = response.text
    for label in ("Cliente", "Equipo", "Falla reportada", "Accesorios", "Condición física"):
        assert label in body
    for field in (
        "customer_id",
        "reported_failure",
        "accessories",
        "physical_condition",
    ):
        assert f'name="{field}"' in body


def test_reception_form_creates_the_order_and_redirects_to_the_record(
    client, session: Session
) -> None:
    ids = catalog_ids(session)
    customer = make_customer(session)

    response = client.post(
        "/reception",
        data={
            "customer_id": str(customer.id),
            "equipment_mode": "new",
            "new_device_type_id": str(ids["device_type_id"]),
            "new_brand_id": str(ids["brand_id"]),
            "new_model": "ThinkPad",
            "new_serial_number": "SN-1",
            "reported_failure": "No enciende",
            "accessories": "Cargador",
            "physical_condition": "Golpe leve en la tapa",
            "password_requested": "on",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/service-orders/")
    record = client.get(response.headers["location"])
    assert record.status_code == 200
    assert "Recibido" in record.text
    assert "No enciende" in record.text
    assert "EQ-000001" in record.text


def test_service_record_lists_history_details_and_only_allowed_transitions(
    client, session: Session
) -> None:
    order = create_order(client, session)
    add_diagnostic_detail(client, session, order["id"])
    transition(client, order["id"], "DIAGNOSING", comment="Revisión en mostrador")

    response = client.get(f"/service-orders/{order['id']}")

    assert response.status_code == 200
    body = response.text
    assert "En diagnóstico" in body
    assert "Historial" in body
    assert "Recepción del equipo" in body
    assert "Revisión en mostrador" in body
    assert "Diagnóstico de placa" in body
    assert 'name="to_status" value="DIAGNOSING"' not in body
    assert 'value="AWAITING_APPROVAL"' in body
    assert 'value="READY_FOR_PICKUP"' not in body


def test_web_transition_advances_the_state_and_returns_to_the_record(
    client, session: Session
) -> None:
    order = create_order(client, session)

    response = client.post(
        f"/service-orders/{order['id']}/transitions",
        data={"to_status": "DIAGNOSING", "comment": "Ingresa a taller"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    record = client.get(response.headers["location"])
    assert record.status_code == 200
    assert "En diagnóstico" in record.text
    assert "Ingresa a taller" in record.text


def test_invalid_web_transition_shows_a_spanish_message_and_keeps_the_state(
    client, session: Session
) -> None:
    order = create_order(client, session)

    response = client.post(
        f"/service-orders/{order['id']}/transitions",
        data={"to_status": "DELIVERED"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "error=" in response.headers["location"]
    record = client.get(response.headers["location"])
    assert record.status_code == 200
    assert "Transición inválida" in record.text
    assert 'value="DIAGNOSING"' in record.text
    assert 'value="DELIVERED"' not in record.text


def test_unknown_service_order_page_returns_404(client) -> None:
    response = client.get("/service-orders/9999")

    assert response.status_code == 404
