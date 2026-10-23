"""Servicio de administración de los cuatro maestros (RF-01 / T-16).

Aplica las reglas de RF-01 y RN-09 sobre el puerto `CatalogRepository`:
duplicado por nombre normalizado (incluye inactivos), baja lógica idempotente
y negativa a borrar un valor en uso. No importa SQLAlchemy ni FastAPI.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.errors import (
    CatalogDuplicateError,
    CatalogValueInUseError,
    NotFoundError,
    ValidationError,
)
from app.services.ports import CatalogRepository, CatalogValue

MASTER_VALUE_RESOURCE = "el valor del maestro"


@dataclass(frozen=True, slots=True)
class CatalogValueView:
    """Valor de maestro con el indicador de uso que consume la API."""

    id: int
    name: str
    is_active: bool
    in_use: bool


class CatalogService:
    """Casos de uso de maestros sobre un repositorio genérico."""

    def __init__(self, repository: CatalogRepository) -> None:
        self._repository = repository

    def list_values(self, *, include_inactive: bool = False) -> list[CatalogValueView]:
        """Lista los valores; por defecto solo los activos."""
        rows = self._repository.list_all() if include_inactive else self._repository.list_active()
        return [self._view(row) for row in rows]

    def get_value(self, catalog_id: int) -> CatalogValueView:
        """Devuelve un valor o falla con `not_found`."""
        return self._view(self._require(catalog_id))

    def create(self, name: str) -> CatalogValueView:
        """Alta con rechazo de duplicados normalizados (RF-01)."""
        display_name = self._validated_name(name)
        duplicate = self._repository.find_by_normalized_name(display_name)
        if duplicate is not None:
            raise CatalogDuplicateError(display_name, existing_id=duplicate.id)
        return self._view(self._repository.add(display_name))

    def rename(self, catalog_id: int, name: str) -> CatalogValueView:
        """Renombrado que conserva la identidad y valida duplicados."""
        current = self._require(catalog_id)
        display_name = self._validated_name(name)
        duplicate = self._repository.find_by_normalized_name(display_name)
        if duplicate is not None and duplicate.id != current.id:
            raise CatalogDuplicateError(display_name, existing_id=duplicate.id)
        updated = self._repository.rename(catalog_id, display_name)
        if updated is None:  # pragma: no cover - defensa ante borrado concurrente
            raise NotFoundError(MASTER_VALUE_RESOURCE, catalog_id)
        return self._view(updated)

    def deactivate(self, catalog_id: int) -> CatalogValueView:
        """Baja lógica idempotente (RN-09)."""
        current = self._require(catalog_id)
        if not current.is_active:
            return self._view(current)
        updated = self._repository.set_active(catalog_id, is_active=False)
        if updated is None:  # pragma: no cover - defensa ante borrado concurrente
            raise NotFoundError(MASTER_VALUE_RESOURCE, catalog_id)
        return self._view(updated)

    def activate(self, catalog_id: int) -> CatalogValueView:
        """Reactivación idempotente de un valor dado de baja."""
        current = self._require(catalog_id)
        if current.is_active:
            return self._view(current)
        updated = self._repository.set_active(catalog_id, is_active=True)
        if updated is None:  # pragma: no cover - defensa ante borrado concurrente
            raise NotFoundError(MASTER_VALUE_RESOURCE, catalog_id)
        return self._view(updated)

    def delete(self, catalog_id: int) -> None:
        """Borra solo un valor sin uso; si está en uso, exige la baja lógica."""
        current = self._require(catalog_id)
        usages = self._repository.count_usages(catalog_id)
        if usages > 0:
            raise CatalogValueInUseError(current.id, usage_count=usages)
        self._repository.delete(catalog_id)

    def _require(self, catalog_id: int) -> CatalogValue:
        value = self._repository.get(catalog_id)
        if value is None:
            raise NotFoundError(MASTER_VALUE_RESOURCE, catalog_id)
        return value

    def _view(self, value: CatalogValue) -> CatalogValueView:
        return CatalogValueView(
            id=value.id,
            name=value.name,
            is_active=value.is_active,
            in_use=self._repository.count_usages(value.id) > 0,
        )

    @staticmethod
    def _validated_name(name: str) -> str:
        display_name = " ".join(name.split())
        if not display_name:
            raise ValidationError("name", "El nombre del valor no puede estar vacío.")
        return display_name
