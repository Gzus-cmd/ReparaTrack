"""T-12: estructura de clientes, equipos y contador de códigos.

Verifica la invariante clave sobre los metadatos: el equipo **no** tiene dueño;
la propiedad vive en `service_orders` (spec §5, plan §2.2).
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Brand, CodeCounter, Customer, DeviceType, Equipment
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
