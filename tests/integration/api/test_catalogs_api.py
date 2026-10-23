"""T-17: API simétrica de los cuatro maestros y vista de administración (RF-01).

Los cuatro recursos se prueban por parametrización para fijar la simetría real
(plan §3.1) y la vista comprueba que la administración se renderiza en español.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.app import create_app
from app.api.deps import get_clock
from app.db.models import Brand, Equipment
from app.db.seed import seed_catalogs

CATALOGS = ["device-types", "brands", "components", "operation-types"]
API = "/api/v1/catalogs"


def _create(client, catalog: str, name: str) -> dict:
    response = client.post(f"{API}/{catalog}", json={"name": name})
    assert response.status_code == 201
    return response.json()


@pytest.mark.parametrize("catalog", CATALOGS)
def test_create_value_returns_201(client, catalog: str) -> None:
    response = client.post(f"{API}/{catalog}", json={"name": "  Valor nuevo  "})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Valor nuevo"
    assert body["is_active"] is True
    assert body["in_use"] is False
    assert isinstance(body["id"], int)


@pytest.mark.parametrize("catalog", CATALOGS)
@pytest.mark.parametrize("duplicate", ["RAM", "ram", "  RAM  "])
def test_duplicate_returns_409_catalog_duplicate(client, catalog: str, duplicate: str) -> None:
    _create(client, catalog, "RAM")

    response = client.post(f"{API}/{catalog}", json={"name": duplicate})

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "catalog_duplicate"
    assert error["details"]["name"].casefold() == "ram"
    assert len(client.get(f"{API}/{catalog}", params={"active": False}).json()) == 1


@pytest.mark.parametrize("catalog", CATALOGS)
def test_list_returns_created_values(client, catalog: str) -> None:
    _create(client, catalog, "Único")

    response = client.get(f"{API}/{catalog}")

    assert response.status_code == 200
    assert [value["name"] for value in response.json()] == ["Único"]


@pytest.mark.parametrize("catalog", CATALOGS)
def test_get_returns_the_value(client, catalog: str) -> None:
    created = _create(client, catalog, "Único")

    response = client.get(f"{API}/{catalog}/{created['id']}")

    assert response.status_code == 200
    assert response.json()["name"] == "Único"


def test_get_unknown_value_returns_404(client) -> None:
    response = client.get(f"{API}/brands/999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("catalog", CATALOGS)
def test_rename_returns_200_with_the_new_name(client, catalog: str) -> None:
    created = _create(client, catalog, "Viejo")

    response = client.patch(f"{API}/{catalog}/{created['id']}", json={"name": "Nuevo"})

    assert response.status_code == 200
    assert response.json()["name"] == "Nuevo"
    assert response.json()["id"] == created["id"]


def test_rename_to_an_existing_name_returns_409(client) -> None:
    ram = _create(client, "components", "RAM")
    _create(client, "components", "Disco")

    response = client.patch(f"{API}/components/{ram['id']}", json={"name": "disco"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "catalog_duplicate"


@pytest.mark.parametrize("catalog", CATALOGS)
def test_deactivate_hides_the_value_from_the_active_list(client, catalog: str) -> None:
    created = _create(client, catalog, "Único")

    response = client.post(f"{API}/{catalog}/{created['id']}/deactivate")

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert client.get(f"{API}/{catalog}").json() == []
    every_value = client.get(f"{API}/{catalog}", params={"active": False}).json()
    assert [value["name"] for value in every_value] == ["Único"]


@pytest.mark.parametrize("catalog", CATALOGS)
def test_deactivate_twice_is_idempotent(client, catalog: str) -> None:
    created = _create(client, catalog, "Único")

    first = client.post(f"{API}/{catalog}/{created['id']}/deactivate")
    second = client.post(f"{API}/{catalog}/{created['id']}/deactivate")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["is_active"] is False


@pytest.mark.parametrize("catalog", CATALOGS)
def test_activate_returns_the_value_to_the_active_list(client, catalog: str) -> None:
    created = _create(client, catalog, "Único")
    client.post(f"{API}/{catalog}/{created['id']}/deactivate")

    response = client.post(f"{API}/{catalog}/{created['id']}/activate")

    assert response.status_code == 200
    assert response.json()["is_active"] is True
    assert [value["name"] for value in client.get(f"{API}/{catalog}").json()] == ["Único"]


@pytest.mark.parametrize("catalog", CATALOGS)
def test_delete_a_free_value_returns_204_and_removes_it(client, catalog: str) -> None:
    created = _create(client, catalog, "Único")

    response = client.delete(f"{API}/{catalog}/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"{API}/{catalog}/{created['id']}").status_code == 404


def test_delete_a_value_in_use_returns_409_and_keeps_it(client, session) -> None:
    device_type = _create(client, "device-types", "Servidor")
    brand = _create(client, "brands", "Genérica")
    session.add(
        Equipment(
            internal_code="EQ-000900",
            device_type_id=device_type["id"],
            brand_id=brand["id"],
            model="Rack",
        )
    )
    session.flush()

    response = client.delete(f"{API}/device-types/{device_type['id']}")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "catalog_value_in_use"
    assert error["details"]["usage_count"] == 1
    assert error["details"]["hint"]
    assert client.get(f"{API}/device-types/{device_type['id']}").status_code == 200


def test_unknown_catalog_returns_404(client) -> None:
    response = client.get(f"{API}/proveedores")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_blank_name_returns_422_with_the_field(client) -> None:
    response = client.post(f"{API}/brands", json={"name": "   "})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["field"] == "name"
    assert client.get(f"{API}/brands").json() == []


def test_missing_name_returns_422_with_the_field(client) -> None:
    response = client.post(f"{API}/brands", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["details"]["field"] == "name"


# --- Vista de administración (Jinja2) ----------------------------------------


def test_ui_lists_the_four_masters(client, session) -> None:
    seed_catalogs(session)

    response = client.get("/catalogs")

    assert response.status_code == 200
    html = response.text
    for title in (
        "Tipos de dispositivo",
        "Marcas",
        "Componentes",
        "Tipos de operación",
    ):
        assert title in html
    assert "Laptop" in html
    assert "Diagnóstico" in html


def test_ui_create_form_registers_a_value(client, session) -> None:
    seed_catalogs(session)

    response = client.post("/catalogs/brands", data={"name": "Genérica"}, follow_redirects=False)

    assert response.status_code == 303
    assert "Genérica" in client.get("/catalogs").text


def test_ui_create_duplicate_shows_an_error_message(client, session) -> None:
    seed_catalogs(session)

    response = client.post("/catalogs/brands", data={"name": "  hp  "}, follow_redirects=True)

    assert response.status_code == 200
    assert "ya existe" in response.text.lower()


def test_ui_deactivate_and_reactivate_links(client, session) -> None:
    seed_catalogs(session)
    created = _create(client, "brands", "Genérica")

    deactivated = client.post(
        f"/catalogs/brands/{created['id']}/deactivate", follow_redirects=False
    )
    assert deactivated.status_code == 303
    assert "Genérica" not in [value["name"] for value in client.get(f"{API}/brands").json()]

    reactivated = client.post(f"/catalogs/brands/{created['id']}/activate", follow_redirects=False)
    assert reactivated.status_code == 303
    assert "Genérica" in [value["name"] for value in client.get(f"{API}/brands").json()]


# --- PRESERVE: la sesión real mantiene el contrato de la capa db -------------


def test_requests_commit_and_keep_health_working(settings, engine, clock) -> None:
    """El commit vive en la dependencia de sesión; la salud sigue respondiendo."""
    app = create_app(settings=settings, engine=engine)
    app.dependency_overrides[get_clock] = lambda: clock
    with TestClient(app) as real_client:
        health = real_client.get("/api/v1/health")
        created = real_client.post(f"{API}/brands", json={"name": "Genérica"})
    app.dependency_overrides.clear()

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "database": "ok"}
    assert created.status_code == 201
    with Session(engine) as other_session:
        assert other_session.scalar(select(func.count()).select_from(Brand)) == 1
