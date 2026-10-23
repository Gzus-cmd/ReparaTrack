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
    drive_to,
    make_customer,
    new_equipment_payload,
    reception_payload,
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


# --- T-28 / T-30: tablero e historial del equipo ---------------------------------


def test_dashboard_page_shows_the_workbench_in_spanish(client, session: Session, clock) -> None:
    customer = make_customer(session, name="Ana Pérez", phone="999111222")
    payload = reception_payload(customer.id, new_equipment=new_equipment_payload(session))
    created = client.post("/api/v1/service-orders", json=payload)
    assert created.status_code == 201, created.text
    clock.travel(days=7)

    response = client.get("/")

    assert response.status_code == 200
    body = response.text
    assert "Equipos en taller" in body
    assert "Ana Pérez" in body
    assert "EQ-000001" in body
    assert "Recibido" in body
    assert "7 días" in body
    assert "Resumen por estado" in body


def test_equipment_history_page_shows_services_states_and_details(client, session: Session) -> None:
    ids = catalog_ids(session)
    equipment = client.post(
        "/api/v1/equipments",
        json={
            "device_type_id": ids["device_type_id"],
            "brand_id": ids["brand_id"],
            "model": "ThinkPad",
            "serial_number": "SN-1",
        },
    ).json()
    customer = make_customer(session, name="Ana Pérez", phone="999111222")
    payload = reception_payload(customer.id, equipment_id=equipment["id"])
    order = client.post("/api/v1/service-orders", json=payload).json()
    add_diagnostic_detail(client, session, order["id"])

    response = client.get(f"/equipments/{equipment['internal_code']}/history")

    assert response.status_code == 200
    body = response.text
    assert "Historial del equipo" in body
    assert "EQ-000001" in body
    assert "Ana Pérez" in body
    assert "Recibido" in body
    assert "Diagnóstico de placa" in body
    assert "Historial de estados" in body


def test_unknown_equipment_history_page_returns_404(client) -> None:
    response = client.get("/equipments/EQ-999999/history")

    assert response.status_code == 404


# --- T-33: aviso de garantía en la recepción (RF-09) -----------------------------


def _equipment_via_api(client, session: Session, model: str = "ThinkPad") -> dict:
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


def _delivered_order(client, session: Session, equipment_id: int) -> dict:
    order = create_order(client, session, equipment_id=equipment_id)
    return drive_to(client, session, order["id"], "DELIVERED")


def _reception_form_data(customer_id: int, internal_code: str, **extra: str) -> dict[str, str]:
    data = {
        "customer_id": str(customer_id),
        "equipment_mode": "existing",
        "equipment_internal_code": internal_code,
        "reported_failure": "Vuelve a fallar",
        "accessories": "Cargador",
        "physical_condition": "Sin marcas visibles",
    }
    data.update(extra)
    return data


def test_reception_shows_warranty_candidates_with_days_and_both_choices(
    client, session: Session, clock
) -> None:
    equipment = _equipment_via_api(client, session)
    origin = _delivered_order(client, session, equipment["id"])
    clock.travel(days=89)

    response = client.get(f"/reception?equipment_id={equipment['id']}")

    assert response.status_code == 200
    body = response.text
    assert "Garantía" in body
    assert "89 días" in body
    assert "Vincular" in body
    assert "servicio nuevo" in body
    assert f'name="origin_service_id" value="{origin["id"]}"' in body


def test_reception_without_candidates_hides_the_warranty_block(client, session: Session) -> None:
    equipment = _equipment_via_api(client, session)
    create_order(client, session, equipment_id=equipment["id"])

    response = client.get(f"/reception?equipment_id={equipment['id']}")

    assert response.status_code == 200
    body = response.text
    assert "Garantía" not in body
    assert "servicio nuevo" not in body
    assert 'name="origin_service_id"' not in body


def test_reception_choice_new_service_creates_no_link(client, session: Session) -> None:
    equipment = _equipment_via_api(client, session)
    customer = make_customer(session)

    response = client.post(
        "/reception",
        data=_reception_form_data(customer.id, equipment["internal_code"]),
        follow_redirects=False,
    )

    assert response.status_code == 303
    order = client.get(f"/api/v1{response.headers['location']}").json()
    assert order["origin_service_id"] is None


def test_reception_choice_linking_sends_the_origin(client, session: Session, clock) -> None:
    equipment = _equipment_via_api(client, session)
    origin = _delivered_order(client, session, equipment["id"])
    clock.travel(days=30)
    customer = make_customer(session)

    response = client.post(
        "/reception",
        data=_reception_form_data(
            customer.id,
            equipment["internal_code"],
            origin_service_id=str(origin["id"]),
        ),
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    order = client.get(f"/api/v1{response.headers['location']}").json()
    assert order["origin_service_id"] == origin["id"]


# --- T-36: contrato OpenAPI documentado (NFR-06) ---------------------------------


def test_openapi_documents_every_requirement_with_a_spanish_summary(client) -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]

    for requirement, path in {
        "RF-01 maestros": "/api/v1/catalogs/{catalog}",
        "RF-02 clientes": "/api/v1/customers",
        "RF-03 equipos": "/api/v1/equipments/lookup",
        "RF-04 recepción": "/api/v1/service-orders",
        "RF-05 detalle": "/api/v1/service-orders/{service_order_id}/details",
        "RF-06 transiciones": "/api/v1/service-orders/{service_order_id}/transitions",
        "RF-07 tablero": "/api/v1/dashboard/workbench",
        "RF-08 historial": "/api/v1/equipments/{equipment_ref}/history",
        "RF-09 garantía": "/api/v1/warranty/candidates",
        "RF-10 abandono": "/api/v1/abandonment/candidates",
    }.items():
        assert path in paths, requirement

    for path, operations in paths.items():
        for method, operation in operations.items():
            assert operation.get("summary", "").strip(), f"{method.upper()} {path} sin resumen"

    schemas = schema["components"]["schemas"]
    assert "ErrorEnvelope" in schemas
    assert "error" in schemas["ErrorEnvelope"]["properties"]
    assert set(schemas["ErrorDetail"]["properties"]) == {"code", "message", "details"}
