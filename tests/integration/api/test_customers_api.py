"""T-18: clientes con contacto, búsqueda y actualización (RF-02).

Cada rechazo se verifica también sobre el estado persistido: un alta inválida
no deja filas (plan §4.3).
"""

from __future__ import annotations

import pytest
from support.factories import new_equipment_payload, reception_payload

API = "/api/v1/customers"


def _create(client, **overrides):
    payload = {"name": "Ana Pérez", "phone": "999111222"}
    payload.update(overrides)
    return client.post(API, json=payload)


def _total(client) -> int:
    return client.get(API).json()["total"]


def test_create_returns_201_with_contact(client) -> None:
    response = _create(client, email="ana@example.com", document="12345678")

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["name"] == "Ana Pérez"
    assert body["phone"] == "999111222"
    assert body["email"] == "ana@example.com"
    assert body["document"] == "12345678"
    assert body["created_at"]


def test_create_requires_phone(client) -> None:
    response = client.post(API, json={"name": "Ana Pérez"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["field"] == "phone"
    assert _total(client) == 0


@pytest.mark.parametrize("phone", ["", "   "])
def test_create_rejects_a_blank_phone(client, phone: str) -> None:
    response = _create(client, phone=phone)

    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "phone"
    assert _total(client) == 0


@pytest.mark.parametrize("email", ["ana", "ana@", "ana@example", "ana example.com", "@example.com"])
def test_create_rejects_an_invalid_email(client, email: str) -> None:
    response = _create(client, email=email)

    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "email"
    assert _total(client) == 0


def test_create_rejects_a_blank_name(client) -> None:
    response = _create(client, name="   ")

    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "name"
    assert _total(client) == 0


def test_duplicate_document_returns_409(client) -> None:
    _create(client, document="12345678")

    response = _create(client, name="Luis Rojas", phone="999333444", document="12345678")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_duplicate"
    assert _total(client) == 1


def test_document_is_optional_and_repeatable(client) -> None:
    first = _create(client)
    second = _create(client, name="Luis Rojas", phone="999333444")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["document"] is None
    assert _total(client) == 2


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("ana", "Ana Pérez"),
        ("Pérez", "Ana Pérez"),
        ("ANA", "Ana Pérez"),
        ("8777", "Luis Rojas"),
        ("87654321", "Luis Rojas"),
    ],
)
def test_search_finds_by_name_phone_and_document(client, query: str, expected: str) -> None:
    _create(client, document="12345678")
    _create(client, name="Luis Rojas", phone="988777666", document="87654321")

    response = client.get(API, params={"q": query})

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["items"]] == [expected]
    assert response.json()["total"] == 1


def test_list_paginates_with_limit_and_offset(client) -> None:
    for index in range(3):
        _create(client, name=f"Cliente {index}", phone=f"90000000{index}")

    first_page = client.get(API, params={"limit": 2}).json()
    second_page = client.get(API, params={"limit": 2, "offset": 2}).json()

    assert first_page["total"] == 3
    assert len(first_page["items"]) == 2
    assert len(second_page["items"]) == 1
    assert second_page["total"] == 3


def test_get_unknown_customer_returns_404(client) -> None:
    response = client.get(f"{API}/999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_patch_updates_the_contact(client) -> None:
    created = _create(client).json()

    response = client.patch(
        f"{API}/{created['id']}",
        json={"phone": "977888999", "email": "nuevo@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["phone"] == "977888999"
    assert response.json()["email"] == "nuevo@example.com"
    assert response.json()["name"] == "Ana Pérez"
    assert client.get(f"{API}/{created['id']}").json()["phone"] == "977888999"


def test_patch_rejects_a_duplicate_document(client) -> None:
    _create(client, document="12345678")
    other = _create(client, name="Luis Rojas", phone="999333444").json()

    response = client.patch(f"{API}/{other['id']}", json={"document": "12345678"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_duplicate"
    assert client.get(f"{API}/{other['id']}").json()["document"] is None


def test_patch_rejects_an_invalid_email(client) -> None:
    created = _create(client).json()

    response = client.patch(f"{API}/{created['id']}", json={"email": "sin-arroba"})

    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "email"


def test_patch_unknown_customer_returns_404(client) -> None:
    response = client.patch(f"{API}/999", json={"phone": "977888999"})

    assert response.status_code == 404


# --- T-31: historial del cliente (RF-08) -------------------------------------


ORDERS = "/api/v1/service-orders"


def _receive_for_customer(client, session, customer_id: int, failure: str = "No enciende") -> dict:
    payload = reception_payload(
        customer_id,
        reported_failure=failure,
        new_equipment=new_equipment_payload(session),
    )
    response = client.post(ORDERS, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _history(client, customer_id: int, **params):
    return client.get(f"{API}/{customer_id}/history", params=params)


def test_customer_history_lists_services_most_recent_first(client, session, clock) -> None:
    customer = _create(client, name="Ana Pérez").json()
    first = _receive_for_customer(client, session, customer["id"], "No enciende")
    clock.travel(days=2)
    second = _receive_for_customer(client, session, customer["id"], "Se apaga sola")

    response = _history(client, customer["id"])

    assert response.status_code == 200, response.text
    items = response.json()
    assert [item["id"] for item in items] == [second["id"], first["id"]]
    assert items[0]["equipment_internal_code"] == "EQ-000002"
    assert items[1]["equipment_internal_code"] == "EQ-000001"
    assert items[0]["received_at"] == second["received_at"]
    assert items[0]["delivered_at"] is None
    assert items[0]["status"] == "RECEIVED"
    assert items[0]["status_label"] == "Recibido"
    assert items[0]["reported_failure"] == "Se apaga sola"
    assert items[0]["origin_service_id"] is None


def test_customer_history_filters_by_received_range(client, session, clock) -> None:
    customer = _create(client, name="Ana Pérez").json()
    first = _receive_for_customer(client, session, customer["id"])
    clock.travel(days=2)
    second = _receive_for_customer(client, session, customer["id"])
    clock.travel(days=2)
    third = _receive_for_customer(client, session, customer["id"])

    response = _history(
        client, customer["id"], **{"from": second["received_at"], "to": third["received_at"]}
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [third["id"], second["id"]]

    narrowed = _history(client, customer["id"], **{"from": third["received_at"]})
    assert [item["id"] for item in narrowed.json()] == [third["id"]]
    assert first["id"] not in [item["id"] for item in narrowed.json()]


def test_customer_history_without_services_returns_an_empty_list(client) -> None:
    customer = _create(client, name="Ana Pérez").json()

    response = _history(client, customer["id"])

    assert response.status_code == 200
    assert response.json() == []


def test_customer_history_unknown_customer_returns_404(client) -> None:
    response = _history(client, 999)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_customer_history_rejects_an_inverted_range(client, session, clock) -> None:
    customer = _create(client, name="Ana Pérez").json()
    first = _receive_for_customer(client, session, customer["id"])
    clock.travel(days=2)
    second = _receive_for_customer(client, session, customer["id"])

    response = _history(
        client, customer["id"], **{"from": second["received_at"], "to": first["received_at"]}
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["field"] == "from"
