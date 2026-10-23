"""T-28 / T-29 — Tablero de equipos en taller y resumen por estado (RF-07).

El tablero responde el dolor D1 ("¿en qué estado está mi equipo?") con el
reloj inyectado: los días se calculan sobre fecha de negocio en America/Lima y
los umbrales se reutilizan de `domain/rules.py` (RN-07 / RN-10), sin duplicar
la comparación. La consulta del listado es una sola, con joins (R-08), y se
verifica de forma estructural contando sentencias, no midiendo tiempos.
"""

from __future__ import annotations

from sqlalchemy import event
from support.factories import (
    drive_to,
    make_customer,
    new_equipment_payload,
    reception_payload,
    transition,
)

API = "/api/v1"
WORKBENCH = f"{API}/dashboard/workbench"
SUMMARY = f"{API}/dashboard/summary"
ORDERS = f"{API}/service-orders"


def _receive(client, session, customer, *, model: str = "ThinkPad") -> dict:
    """Recepciona un equipo nuevo por HTTP y devuelve la orden creada."""
    payload = reception_payload(
        customer.id, new_equipment=new_equipment_payload(session, model=model)
    )
    response = client.post(ORDERS, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _customer(session, name: str, phone: str):
    return make_customer(session, name=name, phone=phone)


def _items(client) -> list[dict]:
    response = client.get(WORKBENCH)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _item(client, service_order_id: int) -> dict:
    for item in _items(client):
        if item["service_order_id"] == service_order_id:
            return item
    raise AssertionError(f"La orden {service_order_id} no está en el tablero.")


# --- T-28: workbench ---------------------------------------------------------


def test_workbench_lists_the_open_order_with_customer_status_and_days(
    client, session, clock
) -> None:
    customer = _customer(session, "Ana Pérez", "999111222")
    order = _receive(client, session, customer)
    clock.travel(days=3)

    items = _items(client)

    assert len(items) == 1
    item = items[0]
    assert item["service_order_id"] == order["id"]
    assert item["customer_name"] == "Ana Pérez"
    assert item["equipment_internal_code"] == "EQ-000001"
    assert item["device_type"] == "Laptop"
    assert item["status"] == "RECEIVED"
    assert item["status_label"] == "Recibido"
    assert item["received_at"] == order["received_at"]
    assert item["days_since_reception"] == 3
    assert item["days_in_status"] == 3
    assert item["is_over_threshold"] is False
    assert item["threshold_rule"] is None


def test_workbench_excludes_delivered_and_abandoned_orders(client, session, clock) -> None:
    open_order = _receive(client, session, _customer(session, "Ana Pérez", "999111222"))
    delivered = _receive(client, session, _customer(session, "Luis Rojas", "999333444"))
    drive_to(client, session, delivered["id"], "DELIVERED")
    abandoned = _receive(client, session, _customer(session, "Eva Torres", "999555666"))
    drive_to(client, session, abandoned["id"], "READY_FOR_PICKUP")
    clock.travel(days=181)
    assert transition(client, abandoned["id"], "ABANDONED", confirm=True).status_code == 200

    assert [item["service_order_id"] for item in _items(client)] == [open_order["id"]]


def test_workbench_sorts_by_days_since_reception_descending(client, session, clock) -> None:
    first = _receive(client, session, _customer(session, "Ana Pérez", "999111222"))
    clock.travel(days=5)
    second = _receive(client, session, _customer(session, "Luis Rojas", "999333444"))
    clock.travel(days=5)
    third = _receive(client, session, _customer(session, "Eva Torres", "999555666"))

    items = _items(client)

    assert [item["service_order_id"] for item in items] == [
        first["id"],
        second["id"],
        third["id"],
    ]
    assert [item["days_since_reception"] for item in items] == [10, 5, 0]


def test_workbench_reuses_the_abandonment_thresholds_with_their_asymmetry(
    client, session, clock
) -> None:
    waiting = _receive(client, session, _customer(session, "Ana Pérez", "999111222"))
    drive_to(client, session, waiting["id"], "AWAITING_APPROVAL")
    ready = _receive(client, session, _customer(session, "Luis Rojas", "999333444"))
    drive_to(client, session, ready["id"], "READY_FOR_PICKUP")
    repairing = _receive(client, session, _customer(session, "Eva Torres", "999555666"))
    drive_to(client, session, repairing["id"], "IN_REPAIR")

    clock.travel(days=30)

    assert _item(client, waiting["id"])["is_over_threshold"] is True
    assert _item(client, waiting["id"])["threshold_rule"] == "RN-10"
    assert _item(client, ready["id"])["is_over_threshold"] is False
    assert _item(client, ready["id"])["threshold_rule"] == "RN-07"
    assert _item(client, repairing["id"])["is_over_threshold"] is False
    assert _item(client, repairing["id"])["threshold_rule"] is None

    clock.travel(days=150)  # 180 días exactos en READY_FOR_PICKUP

    assert _item(client, ready["id"])["days_in_status"] == 180
    assert _item(client, ready["id"])["is_over_threshold"] is False

    clock.travel(days=1)  # 181: "supera 180 días"

    assert _item(client, ready["id"])["days_in_status"] == 181
    assert _item(client, ready["id"])["is_over_threshold"] is True
    assert _item(client, ready["id"])["threshold_rule"] == "RN-07"


def test_workbench_filters_by_status(client, session) -> None:
    received = _receive(client, session, _customer(session, "Ana Pérez", "999111222"))
    diagnosing = _receive(client, session, _customer(session, "Luis Rojas", "999333444"))
    drive_to(client, session, diagnosing["id"], "DIAGNOSING")

    response = client.get(WORKBENCH, params={"status": "DIAGNOSING"})

    assert response.status_code == 200
    assert [item["service_order_id"] for item in response.json()["items"]] == [diagnosing["id"]]
    assert sorted(item["service_order_id"] for item in _items(client)) == sorted(
        [received["id"], diagnosing["id"]]
    )


def test_workbench_with_an_unknown_status_returns_422(client) -> None:
    response = client.get(WORKBENCH, params={"status": "EN_TALLER"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_status"


def test_workbench_listing_is_a_single_query_regardless_of_rows(client, session, engine) -> None:
    for index in range(3):
        _receive(
            client,
            session,
            _customer(session, f"Cliente {index}", f"99911122{index}"),
            model=f"Modelo {index}",
        )

    statements: list[str] = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        response = client.get(WORKBENCH)
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert response.status_code == 200
    assert len(response.json()["items"]) == 3
    assert len(statements) == 1


# --- T-29: summary -----------------------------------------------------------


def _summary(client) -> dict:
    response = client.get(SUMMARY)
    assert response.status_code == 200, response.text
    return response.json()


def test_summary_counts_every_status_key_including_zeros(client, session) -> None:
    empty = _summary(client)

    assert len(empty["by_status"]) == 10
    assert sum(empty["by_status"].values()) == 0
    assert empty["alerts"]["RN-10"]["service_order_ids"] == []
    assert empty["alerts"]["RN-07"]["service_order_ids"] == []

    _receive(client, session, _customer(session, "Ana Pérez", "999111222"))

    filled = _summary(client)
    assert filled["by_status"]["RECEIVED"] == 1
    assert filled["by_status"]["DELIVERED"] == 0
    assert sum(filled["by_status"].values()) == 1


def test_summary_separates_rn10_from_rn07_with_their_boundaries(client, session, clock) -> None:
    waiting = _receive(client, session, _customer(session, "Ana Pérez", "999111222"))
    drive_to(client, session, waiting["id"], "AWAITING_APPROVAL")
    ready = _receive(client, session, _customer(session, "Luis Rojas", "999333444"))
    drive_to(client, session, ready["id"], "READY_FOR_PICKUP")

    clock.travel(days=29)

    alerts = _summary(client)["alerts"]
    assert alerts["RN-10"]["service_order_ids"] == []
    assert alerts["RN-07"]["service_order_ids"] == []

    clock.travel(days=1)  # 30: RN-10 habilita

    alerts = _summary(client)["alerts"]
    assert alerts["RN-10"] == {
        "rule": "RN-10",
        "threshold_days": 30,
        "count": 1,
        "service_order_ids": [waiting["id"]],
    }
    assert alerts["RN-07"]["service_order_ids"] == []

    clock.travel(days=150)  # 180: RN-07 todavía no

    assert _summary(client)["alerts"]["RN-07"]["service_order_ids"] == []

    clock.travel(days=1)  # 181: RN-07 habilita

    alerts = _summary(client)["alerts"]
    assert alerts["RN-07"] == {
        "rule": "RN-07",
        "threshold_days": 180,
        "count": 1,
        "service_order_ids": [ready["id"]],
    }
    assert alerts["RN-10"]["service_order_ids"] == [waiting["id"]]
    assert set(alerts["RN-07"]["service_order_ids"]).isdisjoint(
        alerts["RN-10"]["service_order_ids"]
    )


def test_summary_counts_every_status_of_the_board(client, session, clock) -> None:
    delivered = _receive(client, session, _customer(session, "Ana Pérez", "999111222"))
    drive_to(client, session, delivered["id"], "DELIVERED")
    diagnosing = _receive(client, session, _customer(session, "Luis Rojas", "999333444"))
    drive_to(client, session, diagnosing["id"], "DIAGNOSING")

    by_status = _summary(client)["by_status"]

    assert by_status["DELIVERED"] == 1
    assert by_status["DIAGNOSING"] == 1
    assert by_status["RECEIVED"] == 0
    assert len(by_status) == 10
