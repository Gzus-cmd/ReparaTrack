"""T-34 / T-35 — Abandono de servicios (RF-10 / RN-07, RN-10).

Dos grupos excluyentes por construcción: RN-10 desde el día 30 inclusive en
`AWAITING_APPROVAL` y RN-07 recién después del día 180 en `READY_FOR_PICKUP`.
La marca de abandono es siempre manual y confirmada: no hay job automático.
"""

from __future__ import annotations

from sqlalchemy.orm import Session
from support.factories import (
    SERVICE_ORDERS_URL,
    create_order,
    drive_to,
    transition,
)

CANDIDATES_URL = "/api/v1/abandonment/candidates"
WORKBENCH_URL = "/api/v1/dashboard/workbench"


def _order_in_status(client, session: Session, clock, target: str, days: int) -> dict:
    """Crea la orden, la lleva por transiciones reales y avanza el reloj."""
    order = create_order(client, session)
    drive_to(client, session, order["id"], target)
    clock.travel(days=days)
    return order


def _candidates(client, rule: str | None = None) -> list[dict]:
    params = {} if rule is None else {"rule": rule}
    response = client.get(CANDIDATES_URL, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _history(client, order_id: int) -> list[dict]:
    response = client.get(f"{SERVICE_ORDERS_URL}/{order_id}/history")
    assert response.status_code == 200, response.text
    return response.json()


def test_awaiting_approval_is_not_a_candidate_before_thirty_days(
    client, session: Session, clock
) -> None:
    _order_in_status(client, session, clock, "AWAITING_APPROVAL", 29)

    assert _candidates(client) == []


def test_awaiting_approval_is_a_candidate_on_day_thirty(client, session: Session, clock) -> None:
    order = _order_in_status(client, session, clock, "AWAITING_APPROVAL", 30)

    candidates = _candidates(client)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["service_order_id"] == order["id"]
    assert candidate["status"] == "AWAITING_APPROVAL"
    assert candidate["days_in_status"] == 30
    assert candidate["threshold_days"] == 30
    assert candidate["rule"] == "RN-10"
    assert candidate["customer_name"] == order["customer"]["name"]
    assert candidate["equipment_internal_code"] == order["equipment"]["internal_code"]


def test_ready_for_pickup_is_not_a_candidate_on_day_180(client, session: Session, clock) -> None:
    _order_in_status(client, session, clock, "READY_FOR_PICKUP", 180)

    assert _candidates(client) == []


def test_ready_for_pickup_is_a_candidate_after_day_180(client, session: Session, clock) -> None:
    order = _order_in_status(client, session, clock, "READY_FOR_PICKUP", 181)

    candidates = _candidates(client)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["service_order_id"] == order["id"]
    assert candidate["status"] == "READY_FOR_PICKUP"
    assert candidate["days_in_status"] == 181
    assert candidate["threshold_days"] == 180
    assert candidate["rule"] == "RN-07"


def test_rule_filter_returns_only_its_group(client, session: Session, clock) -> None:
    waiting = _order_in_status(client, session, clock, "AWAITING_APPROVAL", 0)
    ready = _order_in_status(client, session, clock, "READY_FOR_PICKUP", 0)
    clock.travel(days=181)

    both = {candidate["service_order_id"]: candidate["rule"] for candidate in _candidates(client)}
    only_approval = _candidates(client, "RN-10")
    only_pickup = _candidates(client, "RN-07")

    assert both == {waiting["id"]: "RN-10", ready["id"]: "RN-07"}
    assert [candidate["service_order_id"] for candidate in only_approval] == [waiting["id"]]
    assert [candidate["service_order_id"] for candidate in only_pickup] == [ready["id"]]
    assert {candidate["rule"] for candidate in only_approval} == {"RN-10"}
    assert {candidate["rule"] for candidate in only_pickup} == {"RN-07"}


def test_unknown_rule_is_rejected(client) -> None:
    response = client.get(CANDIDATES_URL, params={"rule": "RN-99"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["field"] == "rule"


def test_abandonment_before_the_threshold_is_rejected(client, session: Session, clock) -> None:
    order = _order_in_status(client, session, clock, "AWAITING_APPROVAL", 29)
    before = _history(client, order["id"])

    response = transition(client, order["id"], "ABANDONED", confirm=True)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "threshold_not_reached"
    assert error["details"]["rule"] == "RN-10"
    assert error["details"]["required_days"] == 30
    current = client.get(f"{SERVICE_ORDERS_URL}/{order['id']}").json()
    assert current["status"] == "AWAITING_APPROVAL"
    assert _history(client, order["id"]) == before


def test_abandonment_without_confirmation_is_rejected(client, session: Session, clock) -> None:
    order = _order_in_status(client, session, clock, "AWAITING_APPROVAL", 30)
    before = _history(client, order["id"])

    response = transition(client, order["id"], "ABANDONED")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "confirmation_required"
    assert error["details"]["to_status"] == "ABANDONED"
    current = client.get(f"{SERVICE_ORDERS_URL}/{order['id']}").json()
    assert current["status"] == "AWAITING_APPROVAL"
    assert _history(client, order["id"]) == before


def test_abandonment_with_confirmation_closes_the_service(client, session: Session, clock) -> None:
    order = _order_in_status(client, session, clock, "AWAITING_APPROVAL", 30)
    before = _history(client, order["id"])

    response = transition(client, order["id"], "ABANDONED", confirm=True, comment="Sin respuesta")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ABANDONED"
    assert response.json()["status_label"] == "Abandonado"
    after = _history(client, order["id"])
    assert len(after) == len(before) + 1
    assert after[-1]["status"] == "ABANDONED"
    assert after[-1]["comment"] == "Sin respuesta"


def test_pickup_abandonment_after_day_180(client, session: Session, clock) -> None:
    order = _order_in_status(client, session, clock, "READY_FOR_PICKUP", 181)

    response = transition(client, order["id"], "ABANDONED", confirm=True)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ABANDONED"
    assert _candidates(client) == []


def test_abandoned_service_leaves_the_workbench_and_accepts_no_transitions(
    client, session: Session, clock
) -> None:
    order = _order_in_status(client, session, clock, "AWAITING_APPROVAL", 30)
    assert transition(client, order["id"], "ABANDONED", confirm=True).status_code == 200

    workbench = client.get(WORKBENCH_URL).json()["items"]
    later = transition(client, order["id"], "DELIVERED")

    assert [item["service_order_id"] for item in workbench] == []
    assert later.status_code == 409
    assert later.json()["error"]["code"] == "invalid_transition"
    assert client.get(f"{SERVICE_ORDERS_URL}/{order['id']}").json()["allowed_transitions"] == []
