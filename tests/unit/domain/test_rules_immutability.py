"""T-25 — Inmutabilidad de la condición física (RF-04 / RN-08).

La evidencia de recepción no se edita: la regla pura rechaza cualquier cambio y
el listener de persistencia ataja vías futuras antes del `flush`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Brand, Customer, DeviceType, Equipment, ServiceOrder
from app.db.repositories.service_order_repository import SqlServiceOrderRepository
from app.db.seed import seed_catalogs
from app.domain.errors import ImmutableFieldError
from app.domain.rules import assert_condition_immutable

NOW = datetime(2026, 10, 22, 15, 0, tzinfo=UTC)
CONDITION = "Golpe leve en la tapa"
OTHER_CONDITION = "Sin marcas visibles"


def test_the_same_value_is_allowed() -> None:
    assert assert_condition_immutable(CONDITION, CONDITION) is None


def test_a_different_value_is_rejected_with_context() -> None:
    with pytest.raises(ImmutableFieldError) as error:
        assert_condition_immutable(CONDITION, OTHER_CONDITION)

    assert error.value.code == "immutable_field"
    assert error.value.details == {
        "field": "physical_condition",
        "previous": CONDITION,
        "new": OTHER_CONDITION,
    }


def test_none_over_a_previous_value_is_rejected() -> None:
    with pytest.raises(ImmutableFieldError) as error:
        assert_condition_immutable(CONDITION, None)

    assert error.value.details["new"] is None


def test_the_comparison_does_not_mutate_its_inputs() -> None:
    previous, new = CONDITION, OTHER_CONDITION

    with pytest.raises(ImmutableFieldError):
        assert_condition_immutable(previous, new)

    assert (previous, new) == (CONDITION, OTHER_CONDITION)


def _persisted_order(session: Session) -> ServiceOrder:
    seed_catalogs(session)
    device_type = session.scalars(select(DeviceType).where(DeviceType.name == "Laptop")).one()
    brand = session.scalars(select(Brand).where(Brand.name == "HP")).one()
    customer = Customer(name="Ana Pérez", phone="999111222")
    session.add(customer)
    session.flush()
    equipment = Equipment(
        internal_code="EQ-000001",
        device_type_id=device_type.id,
        brand_id=brand.id,
        model="ThinkPad",
    )
    session.add(equipment)
    session.flush()
    created = SqlServiceOrderRepository(session).add(
        equipment_id=equipment.id,
        customer_id=customer.id,
        received_at=NOW,
        reported_failure="No enciende",
        physical_condition=CONDITION,
        accessories="Cargador",
    )
    session.commit()
    return session.get(ServiceOrder, created.id)


def test_orm_update_of_the_condition_is_blocked_before_the_database(
    session: Session,
) -> None:
    order = _persisted_order(session)
    order.physical_condition = OTHER_CONDITION

    with pytest.raises(ImmutableFieldError) as error:
        session.flush()

    assert error.value.code == "immutable_field"
    session.rollback()
    assert session.get(ServiceOrder, order.id).physical_condition == CONDITION
