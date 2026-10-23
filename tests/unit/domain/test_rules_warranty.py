"""RN-04: garantía de 90 días desde la entrega (T-06)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.enums import ServiceStatus
from app.domain.rules import WARRANTY_DAYS, warranty_eligibility

LIMA = ZoneInfo("America/Lima")
AS_OF = datetime(2026, 10, 22, 15, 0, tzinfo=LIMA)


def delivered_days_ago(days: int) -> datetime:
    return AS_OF - timedelta(days=days)


def test_warranty_window_is_ninety_days():
    assert WARRANTY_DAYS == 90


@pytest.mark.parametrize(("days", "days_left"), [(0, 90), (89, 1)])
def test_delivery_inside_the_window_is_eligible(days, days_left):
    result = warranty_eligibility(delivered_days_ago(days), ServiceStatus.DELIVERED, AS_OF)

    assert result.eligible is True
    assert result.days_since_delivery == days
    assert result.warranty_days_left == days_left
    assert result.reason == "within_warranty"


@pytest.mark.parametrize("days", [90, 91])
def test_delivery_on_or_after_day_ninety_is_not_eligible(days):
    result = warranty_eligibility(delivered_days_ago(days), ServiceStatus.DELIVERED, AS_OF)

    assert result.eligible is False
    assert result.days_since_delivery == days
    assert result.warranty_days_left == 0
    assert result.reason == "warranty_expired"


@pytest.mark.parametrize(
    "status",
    [
        ServiceStatus.RECEIVED,
        ServiceStatus.IN_REPAIR,
        ServiceStatus.READY_FOR_PICKUP,
        ServiceStatus.ABANDONED,
    ],
)
def test_origin_not_delivered_is_not_eligible(status):
    result = warranty_eligibility(delivered_days_ago(10), status, AS_OF)

    assert result.eligible is False
    assert result.days_since_delivery is None
    assert result.warranty_days_left == 0
    assert result.reason == "origin_not_delivered"


def test_new_service_without_origin_does_not_query_the_warranty():
    result = warranty_eligibility(None, ServiceStatus.RECEIVED, AS_OF)

    assert result.eligible is False
    assert result.days_since_delivery is None
    assert result.reason == "origin_not_delivered"


def test_evaluation_does_not_mutate_its_inputs():
    delivered_at = delivered_days_ago(89)
    status = ServiceStatus.DELIVERED

    warranty_eligibility(delivered_at, status, AS_OF)

    assert delivered_at == AS_OF - timedelta(days=89)
    assert status is ServiceStatus.DELIVERED
