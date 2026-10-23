"""Etiquetas y vocabulario de los 10 estados de servicio (T-01 / RF-06)."""

import pytest

from app.domain.enums import STATUS_LABELS, TERMINAL_STATUSES, ServiceStatus
from app.domain.errors import UnknownStatusError

EXPECTED_LABELS = {
    "RECEIVED": "Recibido",
    "DIAGNOSING": "En diagnóstico",
    "AWAITING_APPROVAL": "Esperando aprobación",
    "AWAITING_PART": "Esperando repuesto",
    "IN_REPAIR": "En reparación",
    "NOT_REPARABLE": "No reparable",
    "REJECTED": "Rechazado",
    "READY_FOR_PICKUP": "Listo para entrega",
    "DELIVERED": "Entregado",
    "ABANDONED": "Abandonado",
}


def test_enum_has_exactly_ten_statuses():
    assert len(ServiceStatus) == 10
    assert {status.value for status in ServiceStatus} == set(EXPECTED_LABELS)


@pytest.mark.parametrize(("status", "label"), EXPECTED_LABELS.items())
def test_each_status_has_its_spanish_label(status, label):
    assert ServiceStatus(status).label == label


def test_labels_are_not_empty_and_unique():
    labels = [status.label for status in ServiceStatus]
    assert all(label.strip() for label in labels)
    assert len(set(labels)) == len(labels)
    assert STATUS_LABELS == {ServiceStatus(key): value for key, value in EXPECTED_LABELS.items()}


def test_only_delivered_and_abandoned_are_terminal():
    assert TERMINAL_STATUSES == frozenset({ServiceStatus.DELIVERED, ServiceStatus.ABANDONED})
    assert {status for status in ServiceStatus if status.is_terminal} == TERMINAL_STATUSES


@pytest.mark.parametrize("raw", ["in_repair", "IN_REPAIR", "  In_Repair  "])
def test_parse_accepts_known_status_case_insensitively(raw):
    assert ServiceStatus.parse(raw) is ServiceStatus.IN_REPAIR


def test_parse_returns_the_member_for_member_input():
    assert ServiceStatus.parse(ServiceStatus.RECEIVED) is ServiceStatus.RECEIVED


def test_parse_rejects_the_spanish_label():
    with pytest.raises(UnknownStatusError) as excinfo:
        ServiceStatus.parse("en_reparacion")
    assert excinfo.value.code == "unknown_status"
    assert excinfo.value.details == {"value": "en_reparacion"}


def test_parse_rejects_every_spanish_label():
    for label in STATUS_LABELS.values():
        with pytest.raises(UnknownStatusError):
            ServiceStatus.parse(label)
