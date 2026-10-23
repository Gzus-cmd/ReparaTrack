"""T-13: coherencia de las órdenes de servicio, detalles e historial."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Brand,
    Customer,
    DeviceType,
    Equipment,
    OperationType,
    ServiceDetail,
    ServiceOrder,
    StateHistory,
)
from app.db.repositories.equipment_repository import SqlEquipmentRepository
from app.db.repositories.service_order_repository import SqlServiceOrderRepository
from app.db.repositories.state_history_repository import SqlStateHistoryRepository
from app.db.seed import seed_catalogs

NOW = datetime(2026, 10, 22, 15, 0, tzinfo=UTC)


def _order_context(session: Session) -> dict[str, int]:
    seed_catalogs(session)
    device_type = session.scalars(select(DeviceType)).first()
    brand = session.scalars(select(Brand)).first()
    operation = session.scalars(
        select(OperationType).where(OperationType.name == "Diagnóstico")
    ).one()
    equipment = Equipment(
        internal_code="EQ-000001",
        device_type_id=device_type.id,
        brand_id=brand.id,
        model="ThinkPad",
    )
    customer = Customer(name="Ana Pérez", phone="999111222")
    session.add_all([equipment, customer])
    session.flush()
    return {
        "device_type_id": device_type.id,
        "brand_id": brand.id,
        "equipment_id": equipment.id,
        "customer_id": customer.id,
        "operation_type_id": operation.id,
    }


def _new_order(session: Session, context: dict[str, int], **overrides) -> ServiceOrder:
    values = {
        "equipment_id": context["equipment_id"],
        "customer_id": context["customer_id"],
        "received_at": NOW,
        "reported_failure": "No enciende",
        "physical_condition": "Golpe leve en la tapa",
        "accessories": "Cargador",
    }
    values.update(overrides)
    return ServiceOrder(**values)


def _insert_raw_order(session: Session, context: dict[str, int], status: str) -> None:
    session.execute(
        text(
            "INSERT INTO service_orders ("
            "equipment_id, customer_id, received_at, reported_failure,"
            " physical_condition, accessories, password_requested, status,"
            " created_at, updated_at"
            ") VALUES ("
            ":equipment_id, :customer_id, :received_at, 'No enciende',"
            " 'Golpe leve', 'Cargador', 0, :status, :now, :now)"
        ),
        {
            "equipment_id": context["equipment_id"],
            "customer_id": context["customer_id"],
            "received_at": NOW.isoformat(sep=" "),
            "status": status,
            "now": NOW.isoformat(sep=" "),
        },
    )


def test_status_outside_the_ten_states_is_rejected(session: Session) -> None:
    context = _order_context(session)

    with pytest.raises(IntegrityError):
        _insert_raw_order(session, context, "EN_REPARACION")


def test_delivered_requires_delivered_at(session: Session) -> None:
    context = _order_context(session)
    session.add(_new_order(session, context, status="DELIVERED", delivered_at=None))

    with pytest.raises(IntegrityError):
        session.flush()


def test_delivered_at_requires_delivered_status(session: Session) -> None:
    context = _order_context(session)
    session.add(_new_order(session, context, status="IN_REPAIR", delivered_at=NOW))

    with pytest.raises(IntegrityError):
        session.flush()


def test_origin_service_cannot_be_itself(session: Session) -> None:
    context = _order_context(session)
    order = _new_order(session, context)
    session.add(order)
    session.flush()

    with pytest.raises(IntegrityError):
        session.execute(
            update(ServiceOrder)
            .where(ServiceOrder.id == order.id)
            .values(origin_service_id=order.id)
        )


def test_two_orders_cannot_share_the_same_origin(session: Session) -> None:
    context = _order_context(session)
    origin = _new_order(session, context, status="DELIVERED", delivered_at=NOW)
    session.add(origin)
    session.flush()
    session.add(_new_order(session, context, origin_service_id=origin.id))
    session.flush()
    session.add(_new_order(session, context, origin_service_id=origin.id))

    with pytest.raises(IntegrityError):
        session.flush()


def test_service_order_with_details_and_history_persists(session: Session) -> None:
    context = _order_context(session)
    orders = SqlServiceOrderRepository(session)
    history = SqlStateHistoryRepository(session)

    order = orders.add(
        equipment_id=context["equipment_id"],
        customer_id=context["customer_id"],
        received_at=NOW,
        reported_failure="No enciende",
        physical_condition="Golpe leve",
        accessories="Cargador",
    )
    detail = orders.add_detail(
        service_order_id=order.id,
        operation_type_id=context["operation_type_id"],
        description="Diagnóstico de placa",
    )
    entry = history.add(
        service_order_id=order.id, status="RECEIVED", changed_at=NOW, comment="Recepción"
    )
    session.commit()

    with Session(session.get_bind()) as other_session:
        loaded = other_session.get(ServiceOrder, order.id)
        assert loaded is not None
        assert loaded.status.value == "RECEIVED"
        assert (
            other_session.scalar(
                select(ServiceDetail.description).where(ServiceDetail.id == detail.id)
            )
            == "Diagnóstico de placa"
        )
        assert (
            other_session.scalar(select(StateHistory.comment).where(StateHistory.id == entry.id))
            == "Recepción"
        )


def test_state_history_repository_is_append_only() -> None:
    public_methods = {
        name
        for name in dir(SqlStateHistoryRepository)
        if not name.startswith("_") and callable(getattr(SqlStateHistoryRepository, name))
    }

    assert public_methods == {"add", "list_for_order"}


def test_service_order_tables_and_columns_exist(engine) -> None:
    tables = set(inspect(engine).get_table_names())
    order_columns = {column["name"] for column in inspect(engine).get_columns("service_orders")}
    history_columns = {column["name"] for column in inspect(engine).get_columns("state_history")}

    assert {
        "device_types",
        "brands",
        "components",
        "operation_types",
        "customers",
        "equipments",
        "code_counters",
        "service_orders",
        "service_details",
        "state_history",
    } <= tables
    assert {
        "equipment_id",
        "customer_id",
        "received_at",
        "reported_failure",
        "physical_condition",
        "accessories",
        "password_requested",
        "status",
        "delivered_at",
        "origin_service_id",
    } <= order_columns
    assert "password" not in order_columns
    assert {"service_order_id", "status", "changed_at", "comment"} <= history_columns


def test_order_uses_the_repository_assigned_equipment_code(session: Session) -> None:
    seed_catalogs(session)
    device_type = session.scalars(select(DeviceType).where(DeviceType.name == "Laptop")).one()
    brand = session.scalars(select(Brand).where(Brand.name == "HP")).one()
    customer = Customer(name="Ana Pérez", phone="999111222")
    session.add(customer)
    session.flush()
    equipment_repository = SqlEquipmentRepository(session)
    equipment = equipment_repository.create(
        device_type_id=device_type.id,
        brand_id=brand.id,
        model="ThinkPad",
        serial_number="SN-1",
    )
    orders = SqlServiceOrderRepository(session)

    order = orders.add(
        equipment_id=equipment.id,
        customer_id=customer.id,
        received_at=NOW,
        reported_failure="No enciende",
        physical_condition="Golpe leve",
        accessories="Cargador",
    )
    session.commit()

    assert equipment.internal_code == "EQ-000001"
    assert equipment_repository.find_by_serial_number("SN-1").id == equipment.id
    assert orders.get(order.id).equipment_id == equipment.id
