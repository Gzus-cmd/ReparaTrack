"""T-22 / T-23 — Transiciones de estado con su bitácora (RF-06).

Cada transición válida deja exactamente una fila nueva; todo rechazo deja el
estado y el historial intactos (criterio central de RF-06).
"""

from __future__ import annotations

from support.factories import (
    SERVICE_ORDERS_URL,
    add_diagnostic_detail,
    create_order,
    drive_to,
    transition,
)

ORDERS = SERVICE_ORDERS_URL
FULL_PATH = ["DIAGNOSING", "AWAITING_APPROVAL", "IN_REPAIR", "READY_FOR_PICKUP", "DELIVERED"]


def _history(client, order_id: int) -> list[dict]:
    response = client.get(f"{ORDERS}/{order_id}/history")
    assert response.status_code == 200, response.text
    return response.json()


def _read(client, order_id: int) -> dict:
    response = client.get(f"{ORDERS}/{order_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _snapshot(client, order_id: int) -> tuple[str, int]:
    return _read(client, order_id)["status"], len(_history(client, order_id))


def test_full_path_produces_six_history_rows_in_order(client, session) -> None:
    order = create_order(client, session)

    drive_to(client, session, order["id"], "DELIVERED")

    entries = _history(client, order["id"])
    assert [entry["status"] for entry in entries] == ["RECEIVED", *FULL_PATH]
    assert [entry["status_label"] for entry in entries] == [
        "Recibido",
        "En diagnóstico",
        "Esperando aprobación",
        "En reparación",
        "Listo para entrega",
        "Entregado",
    ]
    final = _read(client, order["id"])
    assert final["status"] == "DELIVERED"
    assert final["delivered_at"] is not None


def test_invalid_transition_is_rejected_without_side_effects(client, session) -> None:
    order = create_order(client, session)
    before = _snapshot(client, order["id"])

    response = transition(client, order["id"], "DELIVERED")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "invalid_transition"
    assert error["details"]["from_status"] == "RECEIVED"
    assert error["details"]["to_status"] == "DELIVERED"
    assert error["details"]["allowed"] == ["DIAGNOSING"]
    assert _snapshot(client, order["id"]) == before


def test_transition_from_delivered_is_rejected(client, session) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "DELIVERED")
    before = _snapshot(client, order["id"])

    response = transition(client, order["id"], "IN_REPAIR")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_transition"
    assert response.json()["error"]["details"]["allowed"] == []
    assert _snapshot(client, order["id"]) == before


def test_transition_from_abandoned_is_rejected(client, session, clock) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "READY_FOR_PICKUP")
    clock.travel(days=181)
    assert transition(client, order["id"], "ABANDONED", confirm=True).status_code == 200
    before = _snapshot(client, order["id"])

    response = transition(client, order["id"], "DELIVERED")

    assert response.status_code == 409
    assert response.json()["error"]["details"]["allowed"] == []
    assert _snapshot(client, order["id"]) == before


def test_comment_is_persisted_in_the_history_row(client, session) -> None:
    order = create_order(client, session)

    response = transition(client, order["id"], "DIAGNOSING", comment="Revisión inicial")

    assert response.status_code == 200
    entries = _history(client, order["id"])
    assert entries[-1]["status"] == "DIAGNOSING"
    assert entries[-1]["comment"] == "Revisión inicial"


def test_unknown_target_status_is_a_validation_error(client, session) -> None:
    order = create_order(client, session)

    response = transition(client, order["id"], "EN_REPARACION")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_status"
    assert _snapshot(client, order["id"]) == ("RECEIVED", 1)


def test_transition_on_unknown_order_returns_404(client) -> None:
    response = transition(client, 9999, "DIAGNOSING")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- T-23: guardas de la transición (RN-03, RN-07, RN-10) --------------------


def test_ready_for_pickup_without_details_is_rejected(client, session) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "IN_REPAIR")
    before = _snapshot(client, order["id"])

    response = transition(client, order["id"], "READY_FOR_PICKUP")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "details_required"
    assert error["details"]["details_count"] == 0
    assert _snapshot(client, order["id"]) == before


def test_ready_for_pickup_with_one_detail_succeeds(client, session) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "IN_REPAIR")
    add_diagnostic_detail(client, session, order["id"])

    response = transition(client, order["id"], "READY_FOR_PICKUP")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "READY_FOR_PICKUP"


def test_abandonment_before_the_approval_threshold_is_rejected(client, session, clock) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "AWAITING_APPROVAL")
    clock.travel(days=29)
    before = _snapshot(client, order["id"])

    response = transition(client, order["id"], "ABANDONED", confirm=True)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "threshold_not_reached"
    assert error["details"] == {
        "rule": "RN-10",
        "days_in_status": 29,
        "required_days": 30,
    }
    assert _snapshot(client, order["id"]) == before


def test_abandonment_at_the_approval_threshold_requires_confirmation(
    client, session, clock
) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "AWAITING_APPROVAL")
    clock.travel(days=30)
    before = _snapshot(client, order["id"])

    response = transition(client, order["id"], "ABANDONED")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "confirmation_required"
    assert error["details"]["to_status"] == "ABANDONED"
    assert _snapshot(client, order["id"]) == before


def test_abandonment_at_the_approval_threshold_with_confirmation_succeeds(
    client, session, clock
) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "AWAITING_APPROVAL")
    clock.travel(days=30)

    response = transition(client, order["id"], "ABANDONED", confirm=True)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ABANDONED"
    assert _history(client, order["id"])[-1]["status"] == "ABANDONED"


def test_abandonment_on_day_180_of_pickup_is_rejected(client, session, clock) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "READY_FOR_PICKUP")
    clock.travel(days=180)
    before = _snapshot(client, order["id"])

    response = transition(client, order["id"], "ABANDONED", confirm=True)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "threshold_not_reached"
    assert error["details"]["rule"] == "RN-07"
    assert error["details"]["days_in_status"] == 180
    assert error["details"]["required_days"] == 180
    assert _snapshot(client, order["id"]) == before


def test_abandonment_on_day_181_of_pickup_succeeds(client, session, clock) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "READY_FOR_PICKUP")
    clock.travel(days=181)

    response = transition(client, order["id"], "ABANDONED", confirm=True)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ABANDONED"


# --- T-26: destinos permitidos con guardas evaluadas -------------------------


def _allowed(client, order_id: int) -> dict:
    response = client.get(f"{ORDERS}/{order_id}/transitions")
    assert response.status_code == 200, response.text
    return response.json()


def _option(payload: dict, status: str) -> dict:
    return next(item for item in payload["allowed"] if item["to_status"] == status)


def test_allowed_transitions_block_ready_for_pickup_without_details(client, session) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "IN_REPAIR")

    blocked = _allowed(client, order["id"])

    assert blocked["current"] == "IN_REPAIR"
    assert _option(blocked, "READY_FOR_PICKUP") == {
        "to_status": "READY_FOR_PICKUP",
        "status_label": "Listo para entrega",
        "blocked_reason": "details_required",
    }
    assert _option(blocked, "AWAITING_PART")["blocked_reason"] is None

    add_diagnostic_detail(client, session, order["id"])

    assert _option(_allowed(client, order["id"]), "READY_FOR_PICKUP")["blocked_reason"] is None


def test_allowed_transitions_block_abandonment_before_the_threshold(client, session, clock) -> None:
    order = create_order(client, session)
    drive_to(client, session, order["id"], "AWAITING_APPROVAL")
    clock.travel(days=29)

    blocked = _allowed(client, order["id"])

    assert _option(blocked, "ABANDONED")["blocked_reason"] == "threshold_not_reached"
    assert _option(blocked, "REJECTED")["blocked_reason"] is None

    clock.travel(days=1)

    assert _option(_allowed(client, order["id"]), "ABANDONED")["blocked_reason"] is None


def test_allowed_transitions_for_unknown_order_returns_404(client) -> None:
    response = client.get(f"{ORDERS}/9999/transitions")

    assert response.status_code == 404
