"""Repositorio genérico de los cuatro maestros (RF-01 / T-14)."""

from __future__ import annotations

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.db.models.catalog import Brand, Component, DeviceType, OperationType
from app.db.models.equipment import Equipment
from app.db.models.service_order import ServiceDetail
from app.db.normalization import normalize_name
from app.services.ports import CatalogValue

CatalogModel = type[DeviceType] | type[Brand] | type[Component] | type[OperationType]

# Cada maestro sabe qué columna lo referencia; el conteo de uso alimenta RN-09.
_USAGE_COLUMNS: dict[CatalogModel, ColumnElement[int]] = {
    DeviceType: Equipment.device_type_id,
    Brand: Equipment.brand_id,
    Component: ServiceDetail.component_id,
    OperationType: ServiceDetail.operation_type_id,
}


def _to_record(row) -> CatalogValue:
    return CatalogValue(id=row.id, name=row.name, is_active=row.is_active)


class SqlCatalogRepository:
    """Implementación de `CatalogRepository` parametrizada por modelo."""

    def __init__(self, session: Session, model: CatalogModel) -> None:
        if model not in _USAGE_COLUMNS:
            raise ValueError(f"Modelo de catálogo no soportado: {model!r}.")
        self._session = session
        self._model = model

    def add(self, name: str) -> CatalogValue:
        normalized = normalize_name(name)
        if not normalized:
            raise ValueError("El nombre del catálogo no puede estar vacío.")
        display_name = " ".join(name.split())
        row = self._model(name=display_name)
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return _to_record(row)

    def get(self, catalog_id: int) -> CatalogValue | None:
        row = self._session.get(self._model, catalog_id)
        return None if row is None else _to_record(row)

    def list_active(self) -> list[CatalogValue]:
        rows = self._session.scalars(
            select(self._model).where(self._model.is_active.is_(True)).order_by(self._model.name)
        )
        return [_to_record(row) for row in rows]

    def find_by_normalized_name(self, name: str) -> CatalogValue | None:
        normalized = normalize_name(name)
        for row in self._session.scalars(select(self._model)):
            if normalize_name(row.name) == normalized:
                return _to_record(row)
        return None

    def count_usages(self, catalog_id: int) -> int:
        column = _USAGE_COLUMNS[self._model]
        owner = column.class_
        return (
            self._session.scalar(
                select(func.count()).select_from(owner).where(column == catalog_id)
            )
            or 0
        )
