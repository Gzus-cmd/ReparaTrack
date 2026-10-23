"""Contrato de errores de dominio (T-02) y matriz cerrada de estados (T-03)."""

import json

import pytest

from app.domain.enums import ServiceStatus
from app.domain.errors import (
    ConfirmationRequiredError,
    DetailsRequiredError,
    DomainError,
    InvalidTransitionError,
    ThresholdNotReachedError,
    UnknownStatusError,
)
from app.domain.state_machine import (
    TRANSITIONS,
    allowed_targets,
    assert_transition,
    can_transition,
)

VALID_EDGES = [
    (ServiceStatus.RECEIVED, ServiceStatus.DIAGNOSING),
    (ServiceStatus.DIAGNOSING, ServiceStatus.AWAITING_APPROVAL),
    (ServiceStatus.DIAGNOSING, ServiceStatus.AWAITING_PART),
    (ServiceStatus.DIAGNOSING, ServiceStatus.NOT_REPARABLE),
    (ServiceStatus.AWAITING_APPROVAL, ServiceStatus.IN_REPAIR),
    (ServiceStatus.AWAITING_APPROVAL, ServiceStatus.REJECTED),
    (ServiceStatus.AWAITING_APPROVAL, ServiceStatus.ABANDONED),
    (ServiceStatus.AWAITING_PART, ServiceStatus.IN_REPAIR),
    (ServiceStatus.IN_REPAIR, ServiceStatus.READY_FOR_PICKUP),
    (ServiceStatus.IN_REPAIR, ServiceStatus.AWAITING_PART),
    (ServiceStatus.NOT_REPARABLE, ServiceStatus.DELIVERED),
    (ServiceStatus.REJECTED, ServiceStatus.DELIVERED),
    (ServiceStatus.READY_FOR_PICKUP, ServiceStatus.DELIVERED),
    (ServiceStatus.READY_FOR_PICKUP, ServiceStatus.ABANDONED),
    (ServiceStatus.READY_FOR_PICKUP, ServiceStatus.IN_REPAIR),
]

VALID_TARGETS = {
    origin: {target for source, target in VALID_EDGES if source is origin}
    for origin in ServiceStatus
}

INVALID_EDGES = [
    (origin, target)
    for origin in ServiceStatus
    for target in ServiceStatus
    if target not in VALID_TARGETS[origin]
]


# --- T-02: contrato de errores ------------------------------------------------


def _error_sample() -> list[tuple[DomainError, str]]:
    return [
        (
            InvalidTransitionError(
                ServiceStatus.RECEIVED,
                ServiceStatus.DELIVERED,
                {ServiceStatus.DIAGNOSING},
            ),
            "invalid_transition",
        ),
        (DetailsRequiredError(details_count=0), "details_required"),
        (
            ThresholdNotReachedError(rule="RN-10", days_in_status=29, required_days=30),
            "threshold_not_reached",
        ),
        (ConfirmationRequiredError(to_status=ServiceStatus.ABANDONED), "confirmation_required"),
        (UnknownStatusError("en_reparacion"), "unknown_status"),
    ]


@pytest.mark.parametrize(("error", "code"), _error_sample())
def test_each_error_exposes_its_stable_code(error, code):
    assert isinstance(error, DomainError)
    assert error.code == code
    assert error.to_envelope()["error"]["code"] == code


@pytest.mark.parametrize(("error", "code"), _error_sample())
def test_error_envelope_is_json_serializable(error, code):
    envelope = error.to_envelope()
    assert json.loads(json.dumps(envelope)) == envelope
    assert envelope["error"]["message"]
    assert set(envelope) == {"error"}
    assert set(envelope["error"]) == {"code", "message", "details"}


def test_invalid_transition_error_names_both_statuses():
    error = InvalidTransitionError(
        ServiceStatus.RECEIVED,
        ServiceStatus.DELIVERED,
        {ServiceStatus.DIAGNOSING},
    )

    assert error.details == {
        "from_status": "RECEIVED",
        "to_status": "DELIVERED",
        "allowed": ["DIAGNOSING"],
    }
    assert "RECEIVED" in str(error)
    assert "DELIVERED" in str(error)


def test_details_and_confirmation_errors_carry_their_context():
    assert DetailsRequiredError(details_count=0).details == {"details_count": 0}
    assert ThresholdNotReachedError(
        rule="RN-07", days_in_status=180, required_days=180
    ).details == {
        "rule": "RN-07",
        "days_in_status": 180,
        "required_days": 180,
    }
    assert ConfirmationRequiredError(to_status=ServiceStatus.ABANDONED).details == {
        "to_status": "ABANDONED"
    }
    assert UnknownStatusError("en_reparacion").details == {"value": "en_reparacion"}


# --- T-03: matriz cerrada (RN-05) --------------------------------------------


def test_matrix_contains_exactly_the_fifteen_valid_edges():
    declared = {(origin, target) for origin, targets in TRANSITIONS.items() for target in targets}
    assert len(declared) == 15
    assert declared == set(VALID_EDGES)


@pytest.mark.parametrize(("origin", "target"), VALID_EDGES)
def test_valid_edge_is_accepted(origin, target):
    assert can_transition(origin, target) is True
    assert target in allowed_targets(origin)
    assert assert_transition(origin, target) is None


@pytest.mark.parametrize(("origin", "target"), INVALID_EDGES)
def test_invalid_edge_is_rejected(origin, target):
    assert len(INVALID_EDGES) == 85
    assert can_transition(origin, target) is False
    assert target not in allowed_targets(origin)

    with pytest.raises(InvalidTransitionError) as excinfo:
        assert_transition(origin, target)

    error = excinfo.value
    assert error.code == "invalid_transition"
    assert error.details["from_status"] == origin.value
    assert error.details["to_status"] == target.value
    assert error.details["allowed"] == sorted(status.value for status in VALID_TARGETS[origin])


@pytest.mark.parametrize("terminal", [ServiceStatus.DELIVERED, ServiceStatus.ABANDONED])
def test_terminal_statuses_have_no_exits(terminal):
    assert allowed_targets(terminal) == frozenset()
    for target in ServiceStatus:
        with pytest.raises(InvalidTransitionError):
            assert_transition(terminal, target)


def test_rework_from_ready_for_pickup_is_allowed():
    assert ServiceStatus.IN_REPAIR in allowed_targets(ServiceStatus.READY_FOR_PICKUP)
    assert can_transition(ServiceStatus.READY_FOR_PICKUP, ServiceStatus.IN_REPAIR) is True


def test_received_cannot_jump_to_delivered():
    assert can_transition(ServiceStatus.RECEIVED, ServiceStatus.DELIVERED) is False
    with pytest.raises(InvalidTransitionError):
        assert_transition(ServiceStatus.RECEIVED, ServiceStatus.DELIVERED)


@pytest.mark.parametrize("status", list(ServiceStatus))
def test_allowed_targets_matches_the_matrix(status):
    assert allowed_targets(status) == frozenset(VALID_TARGETS[status])


def test_unknown_status_key_is_rejected():
    with pytest.raises(UnknownStatusError):
        allowed_targets("en_reparacion")
