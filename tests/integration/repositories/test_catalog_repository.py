"""T-11: maestros base, semilla idempotente y "Diagnóstico"."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Brand,
    Component,
    Customer,
    DeviceType,
    Equipment,
    OperationType,
    ServiceDetail,
    ServiceOrder,
)
from app.db.repositories.catalog_repository import SqlCatalogRepository
from app.db.repositories.customer_repository import SqlCustomerRepository
from app.db.seed import seed_catalogs
from app.services.ports import CatalogRepository, CustomerRepository

NOW = datetime(2026, 10, 22, 15, 0, tzinfo=UTC)
BASE_DEVICE_TYPES = {"Laptop", "PC", "Impresora"}
BASE_COMPONENTS = {"RAM", "Disco", "Pasta térmica", "Pad térmico"}
BASE_OPERATIONS = {
    "Mantenimiento",
    "Reparación",
    "Diagnóstico",
    "Cambio",
    "Formateo",
    "Migración",
}


def _names(session: Session, model: type) -> set[str]:
    return set(session.scalars(select(model.name)))


def test_seed_loads_base_device_types(session: Session) -> None:
    seed_catalogs(session)

    assert _names(session, DeviceType) == BASE_DEVICE_TYPES


def test_seed_loads_base_brands_and_components(session: Session) -> None:
    seed_catalogs(session)

    assert {"HP", "Dell", "Lenovo"} <= _names(session, Brand)
    assert BASE_COMPONENTS <= _names(session, Component)


def test_seed_includes_diagnostic_operation(session: Session) -> None:
    seed_catalogs(session)

    assert BASE_OPERATIONS == _names(session, OperationType)


def test_seed_keeps_a_single_diagnostic_operation(session: Session) -> None:
    seed_catalogs(session)
    seed_catalogs(session)

    diagnostics = session.scalar(
        select(func.count())
        .select_from(OperationType)
        .where(func.lower(func.trim(OperationType.name)) == "diagnóstico")
    )

    assert diagnostics == 1


def test_seed_marks_every_base_value_as_active(session: Session) -> None:
    seed_catalogs(session)

    for model in (DeviceType, Brand, Component, OperationType):
        assert set(session.scalars(select(model.is_active))) == {True}


def test_seed_is_idempotent(session: Session) -> None:
    first_counts = seed_catalogs(session)
    total_after_first = session.scalar(select(func.count()).select_from(DeviceType))

    second_counts = seed_catalogs(session)

    assert first_counts["device_types"] == len(BASE_DEVICE_TYPES)
    assert second_counts["device_types"] == 0
    assert session.scalar(select(func.count()).select_from(DeviceType)) == total_after_first


def test_duplicate_catalog_name_raises_integrity_error(session: Session) -> None:
    session.add(DeviceType(name="Laptop"))
    session.flush()
    session.add(DeviceType(name="Laptop"))

    with pytest.raises(IntegrityError):
        session.flush()


def test_blank_catalog_name_is_rejected(session: Session) -> None:
    session.add(Brand(name="   "))

    with pytest.raises(IntegrityError):
        session.flush()


# --- T-14: repositorios de catálogo y de clientes -----------------------------


def test_catalog_repository_adds_and_reloads_in_another_session(session: Session) -> None:
    repository = SqlCatalogRepository(session, DeviceType)

    created = repository.add("  Laptop  ")
    session.commit()

    with Session(session.get_bind()) as other_session:
        reloaded = SqlCatalogRepository(other_session, DeviceType).get(created.id)

    assert reloaded is not None
    assert reloaded.name == "Laptop"
    assert reloaded.is_active is True


def test_catalog_repository_list_active_excludes_inactive(session: Session) -> None:
    repository = SqlCatalogRepository(session, Brand)
    repository.add("HP")
    inactive = repository.add("Dell")
    session.get(Brand, inactive.id).is_active = False
    session.flush()

    assert [value.name for value in repository.list_active()] == ["HP"]


def test_catalog_repository_finds_by_normalized_name(session: Session) -> None:
    seed_catalogs(session)
    repository = SqlCatalogRepository(session, Component)

    assert repository.find_by_normalized_name("  ram   ").name == "RAM"
    assert repository.find_by_normalized_name("componente inexistente") is None


def test_catalog_repository_counts_device_type_usages(session: Session) -> None:
    seed_catalogs(session)
    device_types = SqlCatalogRepository(session, DeviceType)
    laptop = device_types.find_by_normalized_name("Laptop")
    printer = device_types.find_by_normalized_name("Impresora")
    brand = SqlCatalogRepository(session, Brand).find_by_normalized_name("HP")
    session.add(
        Equipment(
            internal_code="EQ-000010",
            device_type_id=laptop.id,
            brand_id=brand.id,
            model="ThinkPad",
        )
    )
    session.flush()

    assert device_types.count_usages(laptop.id) == 1
    assert device_types.count_usages(printer.id) == 0


def test_catalog_repository_counts_operation_type_usages(session: Session) -> None:
    seed_catalogs(session)
    operations = SqlCatalogRepository(session, OperationType)
    diagnostic = operations.find_by_normalized_name("Diagnóstico")
    maintenance = operations.find_by_normalized_name("Mantenimiento")
    device_type = session.scalars(select(DeviceType)).first()
    brand = session.scalars(select(Brand)).first()
    equipment = Equipment(
        internal_code="EQ-000011",
        device_type_id=device_type.id,
        brand_id=brand.id,
        model="IdeaPad",
    )
    customer = Customer(name="Ana Pérez", phone="999111222")
    session.add_all([equipment, customer])
    session.flush()

    order = ServiceOrder(
        equipment_id=equipment.id,
        customer_id=customer.id,
        received_at=NOW,
        reported_failure="No enciende",
        physical_condition="Golpe leve",
        accessories="Cargador",
    )
    session.add(order)
    session.flush()
    session.add(
        ServiceDetail(
            service_order_id=order.id,
            operation_type_id=diagnostic.id,
            description="Diagnóstico de placa",
        )
    )
    session.flush()

    assert operations.count_usages(diagnostic.id) == 1
    assert operations.count_usages(maintenance.id) == 0


def test_catalog_repository_satisfies_its_port(session: Session) -> None:
    assert isinstance(SqlCatalogRepository(session, Component), CatalogRepository)


def test_customer_repository_adds_and_reads_back(session: Session) -> None:
    repository = SqlCustomerRepository(session)

    created = repository.add(
        name="Ana Pérez", phone="999111222", email="ana@example.com", document="12345678"
    )
    session.commit()

    with Session(session.get_bind()) as other_session:
        reloaded = SqlCustomerRepository(other_session).get(created.id)

    assert reloaded is not None
    assert reloaded.name == "Ana Pérez"
    assert reloaded.document == "12345678"


def test_customer_repository_searches_by_name_and_phone(session: Session) -> None:
    repository = SqlCustomerRepository(session)
    repository.add(name="Ana Pérez", phone="999111222")
    repository.add(name="Luis Rojas", phone="988777666")
    session.flush()

    assert [customer.name for customer in repository.search("ana")] == ["Ana Pérez"]
    assert [customer.name for customer in repository.search("8777")] == ["Luis Rojas"]


def test_customer_repository_satisfies_its_port(session: Session) -> None:
    assert isinstance(SqlCustomerRepository(session), CustomerRepository)
