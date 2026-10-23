"""T-16: administración de maestros con doble de repositorio (RF-01 / RN-09).

El servicio se prueba sin SQLAlchemy ni FastAPI: el doble en memoria reproduce
la semántica del repositorio real (nombre normalizado e inclusión de inactivos).
"""

from __future__ import annotations

import pytest

from app.db.normalization import normalize_name
from app.domain.errors import (
    CatalogDuplicateError,
    CatalogValueInUseError,
    NotFoundError,
    ValidationError,
)
from app.services.catalog_service import CatalogService
from app.services.ports import CatalogRepository, CatalogValue


class FakeCatalogRepository:
    """Doble en memoria con el mismo contrato que `SqlCatalogRepository`."""

    def __init__(self) -> None:
        self.values: dict[int, CatalogValue] = {}
        self.usages: dict[int, int] = {}
        self.deactivate_calls = 0
        self.added_names: list[str] = []
        self._next_id = 1

    def add(self, name: str) -> CatalogValue:
        row = CatalogValue(id=self._next_id, name=" ".join(name.split()), is_active=True)
        self.values[row.id] = row
        self.added_names.append(row.name)
        self._next_id += 1
        return row

    def get(self, catalog_id: int) -> CatalogValue | None:
        return self.values.get(catalog_id)

    def list_active(self) -> list[CatalogValue]:
        return [value for value in self.values.values() if value.is_active]

    def list_all(self) -> list[CatalogValue]:
        return list(self.values.values())

    def find_by_normalized_name(self, name: str) -> CatalogValue | None:
        normalized = normalize_name(name)
        for value in self.values.values():
            if normalize_name(value.name) == normalized:
                return value
        return None

    def count_usages(self, catalog_id: int) -> int:
        return self.usages.get(catalog_id, 0)

    def rename(self, catalog_id: int, name: str) -> CatalogValue | None:
        current = self.values.get(catalog_id)
        if current is None:
            return None
        updated = CatalogValue(
            id=current.id, name=" ".join(name.split()), is_active=current.is_active
        )
        self.values[catalog_id] = updated
        return updated

    def set_active(self, catalog_id: int, *, is_active: bool) -> CatalogValue | None:
        current = self.values.get(catalog_id)
        if current is None:
            return None
        if current.is_active != is_active:
            self.deactivate_calls += 1
        updated = CatalogValue(id=current.id, name=current.name, is_active=is_active)
        self.values[catalog_id] = updated
        return updated

    def delete(self, catalog_id: int) -> bool:
        return self.values.pop(catalog_id, None) is not None


@pytest.fixture
def repository() -> FakeCatalogRepository:
    return FakeCatalogRepository()


@pytest.fixture
def service(repository: FakeCatalogRepository) -> CatalogService:
    return CatalogService(repository)


def test_fake_repository_satisfies_the_port(repository: FakeCatalogRepository) -> None:
    assert isinstance(repository, CatalogRepository)


def test_create_normalizes_whitespace_and_persists(service, repository) -> None:
    created = service.create("  Memoria   RAM  ")

    assert created.id == 1
    assert created.name == "Memoria RAM"
    assert created.is_active is True
    assert created.in_use is False
    assert repository.added_names == ["Memoria RAM"]


def test_create_rejects_duplicate_with_spaces_and_case(service, repository) -> None:
    service.create("RAM")

    with pytest.raises(CatalogDuplicateError) as error:
        service.create(" ram ")

    assert error.value.code == "catalog_duplicate"
    assert error.value.details["name"] == "ram"
    assert len(repository.values) == 1


def test_inactive_value_with_the_same_name_still_blocks_creation(service) -> None:
    original = service.create("RAM")
    service.deactivate(original.id)

    with pytest.raises(CatalogDuplicateError) as error:
        service.create("ram")

    assert error.value.code == "catalog_duplicate"


def test_rename_to_an_existing_name_is_rejected(service) -> None:
    service.create("RAM")
    disk = service.create("Disco")

    with pytest.raises(CatalogDuplicateError):
        service.rename(disk.id, "  ram  ")

    assert service.get_value(disk.id).name == "Disco"


def test_rename_keeps_its_own_name(service) -> None:
    ram = service.create("RAM")

    renamed = service.rename(ram.id, "Memoria RAM")

    assert renamed.name == "Memoria RAM"
    assert renamed.id == ram.id


def test_delete_a_value_in_use_is_rejected_with_a_hint(service, repository) -> None:
    ram = service.create("RAM")
    repository.usages[ram.id] = 2

    with pytest.raises(CatalogValueInUseError) as error:
        service.delete(ram.id)

    assert error.value.code == "catalog_value_in_use"
    assert error.value.details["usage_count"] == 2
    assert error.value.details["hint"]
    assert service.get_value(ram.id).name == "RAM"


def test_delete_a_free_value_removes_it(service, repository) -> None:
    brand = service.create("Genérica")

    service.delete(brand.id)

    assert repository.values == {}
    with pytest.raises(NotFoundError):
        service.get_value(brand.id)


def test_deactivate_is_idempotent(service, repository) -> None:
    value = service.create("RAM")

    first = service.deactivate(value.id)
    second = service.deactivate(value.id)

    assert first.is_active is False
    assert second.is_active is False
    assert repository.deactivate_calls == 1


def test_activate_reactivates_a_deactivated_value(service) -> None:
    value = service.create("RAM")
    service.deactivate(value.id)

    reactivated = service.activate(value.id)

    assert reactivated.is_active is True
    assert [row.id for row in service.list_values()] == [value.id]


def test_activate_an_active_value_is_idempotent(service, repository) -> None:
    value = service.create("RAM")

    reactivated = service.activate(value.id)

    assert reactivated.is_active is True
    assert repository.deactivate_calls == 0


@pytest.mark.parametrize("blank", ["", "   ", "\t\n "])
def test_blank_name_is_rejected(service, repository, blank: str) -> None:
    with pytest.raises(ValidationError) as error:
        service.create(blank)

    assert error.value.code == "validation_error"
    assert error.value.details["field"] == "name"
    assert repository.values == {}


def test_unknown_value_raises_not_found(service) -> None:
    with pytest.raises(NotFoundError) as error:
        service.rename(99, "RAM")

    assert error.value.code == "not_found"
    assert error.value.details["resource"] == "el valor del maestro"


def test_list_values_exposes_in_use_flag(service, repository) -> None:
    ram = service.create("RAM")
    service.create("Disco")
    repository.usages[ram.id] = 1

    values = service.list_values()

    assert [(value.name, value.in_use) for value in values] == [
        ("RAM", True),
        ("Disco", False),
    ]


def test_list_values_can_include_inactive_ones(service) -> None:
    ram = service.create("RAM")
    disk = service.create("Disco")
    service.deactivate(disk.id)

    active_only = [value.name for value in service.list_values()]
    every_value = [value.name for value in service.list_values(include_inactive=True)]

    assert active_only == ["RAM"]
    assert every_value == ["RAM", "Disco"]
    assert ram.id != disk.id
