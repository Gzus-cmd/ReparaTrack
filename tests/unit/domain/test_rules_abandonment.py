"""Base temporal (T-04) y abandono RN-10 / RN-07 (T-07, T-08)."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.enums import ServiceStatus
from app.domain.errors import (
    ConfirmationRequiredError,
    InvalidTransitionError,
    ThresholdNotReachedError,
)
from app.domain.rules import (
    abandonment_eligibility,
    business_date,
    days_between,
    ensure_abandonment_allowed,
)

LIMA = ZoneInfo("America/Lima")
AS_OF = datetime(2026, 10, 22, 15, 0, tzinfo=LIMA)


def days_ago(days: int) -> datetime:
    return AS_OF - timedelta(days=days)


# --- T-04: fecha de negocio en America/Lima ----------------------------------


def test_business_date_uses_the_lima_calendar_day():
    # 2026-10-23T02:00Z es todavía el 22 de octubre en Lima (UTC-5).
    moment = datetime(2026, 10, 23, 2, 0, tzinfo=UTC)

    assert business_date(moment) == date(2026, 10, 22)


def test_naive_datetime_is_read_as_utc():
    assert business_date(datetime(2026, 10, 23, 2, 0)) == date(2026, 10, 22)


def test_same_business_day_is_zero_days():
    start = datetime(2026, 10, 23, 2, 0, tzinfo=UTC)  # 22 oct, 21:00 en Lima
    as_of = datetime(2026, 10, 23, 4, 0, tzinfo=UTC)  # 22 oct, 23:00 en Lima

    assert days_between(start, as_of) == 0


def test_crossing_lima_midnight_counts_one_day():
    start = datetime(2026, 10, 23, 2, 0, tzinfo=UTC)  # 22 oct, 21:00 en Lima
    as_of = datetime(2026, 10, 23, 0, 30, tzinfo=LIMA)  # 23 oct, 00:30 en Lima

    assert days_between(start, as_of) == 1


def test_thirty_calendar_days_are_exactly_thirty_without_hour_rounding():
    start = datetime(2026, 9, 22, 23, 59, tzinfo=LIMA)
    as_of = datetime(2026, 10, 22, 0, 1, tzinfo=LIMA)

    assert days_between(start, as_of) == 30


# --- T-07: RN-10, abandono desde AWAITING_APPROVAL (>= 30 días) ---------------


@pytest.mark.parametrize("days", [0, 29])
def test_rn10_before_day_thirty_is_not_eligible(days):
    result = abandonment_eligibility(days_ago(days), AS_OF, ServiceStatus.AWAITING_APPROVAL)

    assert result.eligible is False
    assert result.rule == "RN-10"
    assert result.days_in_status == days
    assert result.required_days == 30
    assert result.reason == "threshold_not_reached"


@pytest.mark.parametrize("days", [30, 31])
def test_rn10_from_day_thirty_is_eligible(days):
    result = abandonment_eligibility(days_ago(days), AS_OF, ServiceStatus.AWAITING_APPROVAL)

    assert result.eligible is True
    assert result.rule == "RN-10"
    assert result.days_in_status == days
    assert result.required_days == 30
    assert result.reason == "threshold_reached"


def test_rn10_day_twenty_nine_raises_threshold_not_reached():
    with pytest.raises(ThresholdNotReachedError) as excinfo:
        ensure_abandonment_allowed(
            days_ago(29), AS_OF, ServiceStatus.AWAITING_APPROVAL, confirm=True
        )

    assert excinfo.value.code == "threshold_not_reached"
    assert excinfo.value.details == {
        "rule": "RN-10",
        "days_in_status": 29,
        "required_days": 30,
    }


def test_rn10_requires_explicit_confirmation():
    with pytest.raises(ConfirmationRequiredError) as excinfo:
        ensure_abandonment_allowed(
            days_ago(30), AS_OF, ServiceStatus.AWAITING_APPROVAL, confirm=False
        )

    assert excinfo.value.code == "confirmation_required"
    assert excinfo.value.details == {"to_status": "ABANDONED"}


def test_rn10_day_thirty_with_confirmation_is_allowed():
    result = ensure_abandonment_allowed(
        days_ago(30), AS_OF, ServiceStatus.AWAITING_APPROVAL, confirm=True
    )

    assert result.eligible is True
    assert result.rule == "RN-10"


@pytest.mark.parametrize("status", list(ServiceStatus))
def test_rn10_only_applies_to_awaiting_approval(status):
    result = abandonment_eligibility(days_ago(30), AS_OF, status)

    assert (result.rule == "RN-10") is (status is ServiceStatus.AWAITING_APPROVAL)


# --- T-08: RN-07, abandono desde READY_FOR_PICKUP (> 180 días) ---------------


@pytest.mark.parametrize("days", [179, 180])
def test_rn07_day_one_hundred_eighty_does_not_enable_abandonment(days):
    result = abandonment_eligibility(days_ago(days), AS_OF, ServiceStatus.READY_FOR_PICKUP)

    assert result.eligible is False
    assert result.rule == "RN-07"
    assert result.days_in_status == days
    assert result.required_days == 180
    assert result.reason == "threshold_not_reached"


@pytest.mark.parametrize("days", [181])
def test_rn07_after_day_one_hundred_eighty_is_eligible(days):
    result = abandonment_eligibility(days_ago(days), AS_OF, ServiceStatus.READY_FOR_PICKUP)

    assert result.eligible is True
    assert result.rule == "RN-07"
    assert result.days_in_status == days
    assert result.required_days == 180
    assert result.reason == "threshold_reached"


def test_rn07_day_one_hundred_eighty_raises_threshold_not_reached():
    with pytest.raises(ThresholdNotReachedError) as excinfo:
        ensure_abandonment_allowed(
            days_ago(180), AS_OF, ServiceStatus.READY_FOR_PICKUP, confirm=True
        )

    assert excinfo.value.details == {
        "rule": "RN-07",
        "days_in_status": 180,
        "required_days": 180,
    }


def test_rn07_requires_explicit_confirmation():
    with pytest.raises(ConfirmationRequiredError):
        ensure_abandonment_allowed(
            days_ago(181), AS_OF, ServiceStatus.READY_FOR_PICKUP, confirm=False
        )


def test_rn07_after_the_threshold_with_confirmation_is_allowed():
    result = ensure_abandonment_allowed(
        days_ago(181), AS_OF, ServiceStatus.READY_FOR_PICKUP, confirm=True
    )

    assert result.eligible is True
    assert result.rule == "RN-07"


@pytest.mark.parametrize("status", list(ServiceStatus))
def test_rn07_only_applies_to_ready_for_pickup(status):
    result = abandonment_eligibility(days_ago(400), AS_OF, status)

    assert (result.rule == "RN-07") is (status is ServiceStatus.READY_FOR_PICKUP)


# --- Estados sin regla de abandono -------------------------------------------


@pytest.mark.parametrize(
    "status",
    [ServiceStatus.RECEIVED, ServiceStatus.IN_REPAIR, ServiceStatus.DELIVERED],
)
def test_other_states_have_no_abandonment_rule(status):
    result = abandonment_eligibility(days_ago(400), AS_OF, status)

    assert result.eligible is False
    assert result.rule is None
    assert result.required_days is None
    assert result.reason == "rule_not_applicable"


def test_abandonment_from_other_state_follows_the_state_machine():
    with pytest.raises(InvalidTransitionError) as excinfo:
        ensure_abandonment_allowed(days_ago(400), AS_OF, ServiceStatus.IN_REPAIR, confirm=True)

    assert excinfo.value.code == "invalid_transition"
    assert excinfo.value.details["allowed"] == ["AWAITING_PART", "READY_FOR_PICKUP"]
