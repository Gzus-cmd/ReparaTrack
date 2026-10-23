"""T-12: estructura de clientes, equipos y contador de códigos.

Verifica la invariante clave sobre los metadatos: el equipo **no** tiene dueño;
la propiedad vive en `service_orders` (spec §5, plan §2.2).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from support.factories import (
    add_diagnostic_detail,
    drive_to,
    reception_payload,
)

from app.db.models import Brand, CodeCounter, Customer, DeviceType, Equipment, ServiceOrder
from app.db.repositories.equipment_repository import (
    DuplicateInternalCodeError,
    SqlEquipmentRepository,
)
from app.db.seed import seed_catalogs
from app.services.ports import EquipmentRepository


def _catalog_ids(session: Session) -> tuple[int, int]:
    device_type = DeviceType(name="Laptop")
    brand = Brand(name="HP")
    session.add_all([device_type, brand])
    session.flush()
    return device_type.id, brand.id


def test_equipments_table_has_no_owner_column(engine) -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("equipments")}

    assert "customer_id" not in columns
    assert "owner_id" not in columns


def test_no_customer_equipment_join_table_exists(engine) -> None:
    tables = set(inspect(engine).get_table_names())

    assert not any("customer" in name and "equipment" in name for name in tables)


def test_equipment_columns_match_the_plan(engine) -> None:
    columns = {column["name"]: column for column in inspect(engine).get_columns("equipments")}

    assert columns["serial_number"]["nullable"] is True
    assert columns["internal_code"]["nullable"] is False
    assert columns["device_type_id"]["nullable"] is False
    assert columns["brand_id"]["nullable"] is False
    assert columns["model"]["nullable"] is False


def test_duplicate_internal_code_raises_integrity_error(session: Session) -> None:
    device_type_id, brand_id = _catalog_ids(session)
    session.add(
        Equipment(
            internal_code="EQ-000001",
            device_type_id=device_type_id,
            brand_id=brand_id,
            model="ThinkPad",
        )
    )
    session.flush()
    session.add(
        Equipment(
            internal_code="EQ-000001",
            device_type_id=device_type_id,
            brand_id=brand_id,
            model="IdeaPad",
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_a_referenced_device_type_fails(session: Session) -> None:
    device_type_id, brand_id = _catalog_ids(session)
    session.add(
        Equipment(
            internal_code="EQ-000001",
            device_type_id=device_type_id,
            brand_id=brand_id,
            model="ThinkPad",
        )
    )
    session.flush()

    with pytest.raises(IntegrityError):
        session.execute(delete(DeviceType).where(DeviceType.id == device_type_id))


def test_code_counter_rejects_negative_values(session: Session) -> None:
    session.add(CodeCounter(name="equipment", last_value=-1))

    with pytest.raises(IntegrityError):
        session.flush()


def test_customer_document_is_unique_when_present(session: Session) -> None:
    session.add(Customer(name="Ana Pérez", phone="999111222", document="12345678"))
    session.flush()
    session.add(Customer(name="Luis Rojas", phone="999333444", document="12345678"))

    with pytest.raises(IntegrityError):
        session.flush()


def test_customer_document_may_be_absent_more_than_once(session: Session) -> None:
    session.add_all(
        [
            Customer(name="Ana Pérez", phone="999111222"),
            Customer(name="Luis Rojas", phone="999333444"),
        ]
    )

    session.flush()

    assert session.query(Customer).count() == 2


# --- T-15: código correlativo atómico y búsquedas del repositorio -------------


def _seeded_catalog_ids(session: Session) -> tuple[int, int]:
    seed_catalogs(session)
    device_type = session.scalars(select(DeviceType).where(DeviceType.name == "Laptop")).one()
    brand = session.scalars(select(Brand).where(Brand.name == "HP")).one()
    return device_type.id, brand.id


def test_equipment_codes_start_at_one_and_have_no_gaps(session: Session) -> None:
    device_type_id, brand_id = _seeded_catalog_ids(session)
    repository = SqlEquipmentRepository(session)

    first = repository.create(device_type_id=device_type_id, brand_id=brand_id, model="ThinkPad")
    second = repository.create(device_type_id=device_type_id, brand_id=brand_id, model="IdeaPad")

    assert first.internal_code == "EQ-000001"
    assert second.internal_code == "EQ-000002"
    assert (
        session.scalar(select(CodeCounter.last_value).where(CodeCounter.name == "equipment")) == 2
    )


def test_rollback_does_not_consume_the_counter(session: Session) -> None:
    device_type_id, brand_id = _seeded_catalog_ids(session)
    session.commit()
    repository = SqlEquipmentRepository(session)

    repository.create(device_type_id=device_type_id, brand_id=brand_id, model="ThinkPad")
    session.rollback()

    retried = repository.create(device_type_id=device_type_id, brand_id=brand_id, model="IdeaPad")

    assert retried.internal_code == "EQ-000001"


def test_duplicate_internal_code_is_a_business_conflict(session: Session) -> None:
    device_type_id, brand_id = _seeded_catalog_ids(session)
    session.commit()
    repository = SqlEquipmentRepository(session)
    repository.create(device_type_id=device_type_id, brand_id=brand_id, model="ThinkPad")
    session.add(
        Equipment(
            internal_code="EQ-000002",
            device_type_id=device_type_id,
            brand_id=brand_id,
            model="Squatter",
        )
    )
    session.commit()

    with pytest.raises(DuplicateInternalCodeError) as error:
        repository.create(device_type_id=device_type_id, brand_id=brand_id, model="IdeaPad")

    session.rollback()
    assert error.value.code == "duplicate_internal_code"
    assert session.scalar(select(func.count()).select_from(Equipment)) == 2
    assert (
        session.scalar(select(CodeCounter.last_value).where(CodeCounter.name == "equipment")) == 1
    )


def test_lookup_by_internal_code_and_serial(session: Session) -> None:
    device_type_id, brand_id = _seeded_catalog_ids(session)
    repository = SqlEquipmentRepository(session)
    created = repository.create(
        device_type_id=device_type_id,
        brand_id=brand_id,
        model="ThinkPad",
        serial_number="SN-9",
    )

    assert repository.find_by_internal_code("EQ-000001").id == created.id
    assert repository.find_by_internal_code("eq-000001").id == created.id
    assert repository.find_by_serial_number("SN-9").id == created.id
    assert repository.find_by_internal_code("EQ-999999") is None


def test_serial_lookup_returns_the_first_registered_equipment(session: Session) -> None:
    device_type_id, brand_id = _seeded_catalog_ids(session)
    repository = SqlEquipmentRepository(session)
    first = repository.create(
        device_type_id=device_type_id,
        brand_id=brand_id,
        model="ThinkPad",
        serial_number="SN-9",
    )
    repository.create(
        device_type_id=device_type_id,
        brand_id=brand_id,
        model="IdeaPad",
        serial_number="SN-9",
    )

    assert repository.find_by_serial_number("SN-9").id == first.id


def test_equipment_repository_satisfies_its_port(session: Session) -> None:
    assert isinstance(SqlEquipmentRepository(session), EquipmentRepository)


# --- T-19 / T-20: alta con correlativo y búsqueda por HTTP (RF-03) -----------

API = "/api/v1/equipments"
NOW = datetime(2026, 10, 22, 15, 0, tzinfo=UTC)


def _seeded_ids(session: Session) -> tuple[int, int]:
    seed_catalogs(session)
    device_type = session.scalars(select(DeviceType).where(DeviceType.name == "Laptop")).one()
    brand = session.scalars(select(Brand).where(Brand.name == "HP")).one()
    return device_type.id, brand.id


def _post_equipment(client, device_type_id: int, brand_id: int, **overrides):
    payload = {"device_type_id": device_type_id, "brand_id": brand_id, "model": "ThinkPad"}
    payload.update(overrides)
    return client.post(API, json=payload)


def test_create_equipment_assigns_correlative_codes(client, session: Session) -> None:
    device_type_id, brand_id = _seeded_ids(session)

    first = _post_equipment(client, device_type_id, brand_id)
    second = _post_equipment(client, device_type_id, brand_id, model="IdeaPad")

    assert first.status_code == 201
    assert first.json()["internal_code"] == "EQ-000001"
    assert second.status_code == 201
    assert second.json()["internal_code"] == "EQ-000002"


def test_create_equipment_without_serial_returns_null(client, session: Session) -> None:
    device_type_id, brand_id = _seeded_ids(session)

    response = _post_equipment(client, device_type_id, brand_id)

    assert response.status_code == 201
    assert response.json()["serial_number"] is None


def test_create_equipment_returns_nested_references_and_no_owner(client, session: Session) -> None:
    device_type_id, brand_id = _seeded_ids(session)

    body = _post_equipment(client, device_type_id, brand_id, serial_number=" SN-1 ").json()

    assert body["device_type"] == {"id": device_type_id, "name": "Laptop"}
    assert body["brand"] == {"id": brand_id, "name": "HP"}
    assert body["model"] == "ThinkPad"
    assert body["serial_number"] == "SN-1"
    assert body["current_owner"] is None
    assert body["previous_services_count"] == 0
    assert body["created_at"]


@pytest.mark.parametrize("field", ["device_type_id", "brand_id"])
def test_create_equipment_with_unknown_catalog_returns_422(
    client, session: Session, field: str
) -> None:
    device_type_id, brand_id = _seeded_ids(session)
    payload = {"device_type_id": device_type_id, "brand_id": brand_id, "model": "ThinkPad"}
    payload[field] = 9999

    response = client.post(API, json=payload)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["field"] == field
    # El alta rechazada no consume correlativo ni deja equipos.
    retried = _post_equipment(client, device_type_id, brand_id)
    assert retried.json()["internal_code"] == "EQ-000001"
    assert session.scalar(select(func.count()).select_from(Equipment)) == 1


def test_create_equipment_with_inactive_catalog_returns_422(client, session: Session) -> None:
    device_type_id, brand_id = _seeded_ids(session)
    client.post(f"/api/v1/catalogs/device-types/{device_type_id}/deactivate")

    response = _post_equipment(client, device_type_id, brand_id)

    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "device_type_id"


def test_create_equipment_rejects_a_blank_model(client, session: Session) -> None:
    device_type_id, brand_id = _seeded_ids(session)

    response = _post_equipment(client, device_type_id, brand_id, model="   ")

    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "model"


def test_lookup_by_internal_code_and_by_serial_returns_the_same_equipment(
    client, session: Session
) -> None:
    device_type_id, brand_id = _seeded_ids(session)
    created = _post_equipment(client, device_type_id, brand_id, serial_number="SN-1").json()

    by_code = client.get(f"{API}/lookup", params={"internal_code": created["internal_code"]})
    by_serial = client.get(f"{API}/lookup", params={"serial_number": "SN-1"})

    assert by_code.status_code == 200
    assert by_serial.status_code == 200
    assert by_code.json()["id"] == created["id"]
    assert by_serial.json()["id"] == created["id"]
    assert by_code.json()["previous_services_count"] == 0
    assert by_serial.json()["previous_services_count"] == 0


def test_lookup_without_parameters_returns_422(client) -> None:
    response = client.get(f"{API}/lookup")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["field"] == "internal_code"


def test_lookup_unknown_code_returns_404(client) -> None:
    response = client.get(f"{API}/lookup", params={"internal_code": "EQ-999999"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_lookup_unknown_serial_returns_404(client) -> None:
    response = client.get(f"{API}/lookup", params={"serial_number": "SN-INEXISTENTE"})

    assert response.status_code == 404


def test_lookup_gives_precedence_to_the_internal_code(client, session: Session) -> None:
    device_type_id, brand_id = _seeded_ids(session)
    _post_equipment(client, device_type_id, brand_id, serial_number="SN-1")
    second = _post_equipment(
        client, device_type_id, brand_id, model="IdeaPad", serial_number="SN-2"
    ).json()

    response = client.get(
        f"{API}/lookup",
        params={"internal_code": second["internal_code"], "serial_number": "SN-1"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == second["id"]


def test_lookup_reports_previous_services_and_current_owner(client, session: Session) -> None:
    device_type_id, brand_id = _seeded_ids(session)
    equipment = _post_equipment(client, device_type_id, brand_id).json()
    customer = Customer(name="Ana Pérez", phone="999111222")
    session.add(customer)
    session.flush()
    for failure in ("No enciende", "Se apaga sola"):
        session.add(
            ServiceOrder(
                equipment_id=equipment["id"],
                customer_id=customer.id,
                received_at=NOW,
                reported_failure=failure,
                physical_condition="Buen estado",
                accessories="Ninguno",
            )
        )
    session.flush()

    response = client.get(f"{API}/lookup", params={"internal_code": equipment["internal_code"]})

    assert response.status_code == 200
    body = response.json()
    assert body["previous_services_count"] == 2
    assert body["current_owner"] == {
        "id": customer.id,
        "name": "Ana Pérez",
        "phone": "999111222",
    }


# --- T-30: historial técnico completo del equipo (RF-08) ----------------------

ORDERS_API = "/api/v1/service-orders"


def _history(client, reference, **params):
    return client.get(f"{API}/{reference}/history", params=params)


def _receive_for_equipment(client, customer, equipment_id: int, failure: str) -> dict:
    payload = reception_payload(customer.id, equipment_id=equipment_id, reported_failure=failure)
    response = client.post(ORDERS_API, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_equipment_history_composes_services_states_and_details(
    client, session: Session, clock
) -> None:
    device_type_id, brand_id = _seeded_ids(session)
    equipment = _post_equipment(client, device_type_id, brand_id, serial_number="SN-1").json()

    first_customer = Customer(name="Ana Pérez", phone="999111222")
    second_customer = Customer(name="Luis Rojas", phone="999333444")
    third_customer = Customer(name="Eva Torres", phone="999555666")
    session.add_all([first_customer, second_customer, third_customer])
    session.flush()

    first = _receive_for_equipment(client, first_customer, equipment["id"], "No enciende")
    drive_to(client, session, first["id"], "DELIVERED")

    clock.travel(days=2)
    second = _receive_for_equipment(client, second_customer, equipment["id"], "Se apaga sola")
    add_diagnostic_detail(client, session, second["id"])

    clock.travel(days=2)
    third = _receive_for_equipment(client, third_customer, equipment["id"], "Pantalla rota")
    session.get(ServiceOrder, third["id"]).origin_service_id = first["id"]
    session.flush()

    response = _history(client, equipment["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["equipment"]["id"] == equipment["id"]
    assert body["equipment"]["internal_code"] == "EQ-000001"
    assert body["equipment"]["serial_number"] == "SN-1"
    assert body["equipment"]["current_owner"]["name"] == "Eva Torres"
    assert body["equipment"]["previous_services_count"] == 3

    services = body["services"]
    assert [service["id"] for service in services] == [third["id"], second["id"], first["id"]]
    assert [service["customer"]["name"] for service in services] == [
        "Eva Torres",
        "Luis Rojas",
        "Ana Pérez",
    ]
    assert [service["status"] for service in services] == ["RECEIVED", "RECEIVED", "DELIVERED"]
    assert [service["status_label"] for service in services] == [
        "Recibido",
        "Recibido",
        "Entregado",
    ]
    assert services[0]["origin_service_id"] == first["id"]
    assert services[2]["origin_service_id"] is None

    assert [entry["status"] for entry in services[2]["states"]] == [
        "RECEIVED",
        "DIAGNOSING",
        "AWAITING_APPROVAL",
        "IN_REPAIR",
        "READY_FOR_PICKUP",
        "DELIVERED",
    ]
    assert [entry["status_label"] for entry in services[1]["states"]] == ["Recibido"]
    delivered_detail = services[2]["details"][0]
    assert delivered_detail["operation_type"]["name"] == "Diagnóstico"
    assert delivered_detail["component"] is None
    assert delivered_detail["description"] == "Diagnóstico de placa"
    assert delivered_detail["created_at"]
    assert [detail["description"] for detail in services[1]["details"]] == ["Diagnóstico de placa"]
    assert services[0]["details"] == []


def test_equipment_history_include_filters_sections(client, session: Session) -> None:
    device_type_id, brand_id = _seeded_ids(session)
    equipment = _post_equipment(client, device_type_id, brand_id).json()
    customer = Customer(name="Ana Pérez", phone="999111222")
    session.add(customer)
    session.flush()
    order = _receive_for_equipment(client, customer, equipment["id"], "No enciende")
    add_diagnostic_detail(client, session, order["id"])

    both = _history(client, equipment["id"]).json()["services"][0]
    assert both["states"] is not None
    assert both["details"] is not None

    only_details = _history(client, equipment["id"], include="details").json()["services"][0]
    assert only_details["states"] is None
    assert [detail["description"] for detail in only_details["details"]] == ["Diagnóstico de placa"]

    only_states = _history(client, equipment["id"], include="states").json()["services"][0]
    assert only_states["details"] is None
    assert [entry["status"] for entry in only_states["states"]] == ["RECEIVED"]


def test_equipment_history_accepts_id_internal_code_and_serial(client, session: Session) -> None:
    device_type_id, brand_id = _seeded_ids(session)
    equipment = _post_equipment(client, device_type_id, brand_id, serial_number="SN-1").json()

    by_id = _history(client, equipment["id"])
    by_code = _history(client, "EQ-000001")
    by_serial = _history(client, "SN-1")

    assert by_id.status_code == by_code.status_code == by_serial.status_code == 200
    assert by_id.json() == by_code.json() == by_serial.json()


def test_equipment_history_unknown_reference_returns_404(client) -> None:
    response = _history(client, "EQ-999999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_equipment_history_rejects_an_unknown_section(client, session: Session) -> None:
    device_type_id, brand_id = _seeded_ids(session)
    equipment = _post_equipment(client, device_type_id, brand_id).json()

    response = _history(client, equipment["id"], include="details,adjuntos")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["field"] == "include"


def test_list_equipments_returns_the_most_recent_first(client, session: Session) -> None:
    device_type_id, brand_id = _seeded_ids(session)
    _post_equipment(client, device_type_id, brand_id, model="Pavilion 15", serial_number="SN-1")
    _post_equipment(client, device_type_id, brand_id, model="IdeaPad")

    response = client.get(API)

    assert response.status_code == 200
    body = response.json()
    assert [item["model"] for item in body] == ["IdeaPad", "Pavilion 15"]
    assert body[0]["internal_code"].startswith("EQ-")
    assert "customer_id" not in body[0]
