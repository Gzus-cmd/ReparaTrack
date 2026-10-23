"""RN-03: `READY_FOR_PICKUP` exige al menos una línea de detalle (T-05)."""

import inspect

import pytest

from app.domain.enums import ServiceStatus
from app.domain.errors import DetailsRequiredError
from app.domain.rules import ensure_details_for_pickup


def test_zero_details_block_ready_for_pickup():
    with pytest.raises(DetailsRequiredError) as excinfo:
        ensure_details_for_pickup(0, ServiceStatus.READY_FOR_PICKUP)

    assert excinfo.value.code == "details_required"
    assert excinfo.value.details == {"details_count": 0}


@pytest.mark.parametrize("details_count", [1, 5])
def test_one_or_more_details_allow_ready_for_pickup(details_count):
    assert ensure_details_for_pickup(details_count, ServiceStatus.READY_FOR_PICKUP) is None


@pytest.mark.parametrize("target", [ServiceStatus.IN_REPAIR, ServiceStatus.AWAITING_PART])
def test_rule_never_blocks_other_destinations(target):
    assert ensure_details_for_pickup(0, target) is None


def test_rule_only_looks_at_the_count_not_the_description():
    signature = inspect.signature(ensure_details_for_pickup)
    assert list(signature.parameters) == ["details_count", "target"]
    # Una única línea con la operación "Diagnóstico" también cuenta: la regla
    # no distingue tipos de operación ni textos de descripción.
    assert ensure_details_for_pickup(1, ServiceStatus.READY_FOR_PICKUP) is None


def test_unknown_target_status_is_rejected():
    from app.domain.errors import UnknownStatusError

    with pytest.raises(UnknownStatusError):
        ensure_details_for_pickup(1, "en_reparacion")
