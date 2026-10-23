"""Registro de maestros administrables: slug de API -> modelo SQLAlchemy.

La API no conoce modelos; este registro es el único puente y lo consume el
módulo de composición (`app.api.deps`).
"""

from __future__ import annotations

from app.db.models.catalog import Brand, Component, DeviceType, OperationType

CATALOG_MODELS: dict[str, type] = {
    "device-types": DeviceType,
    "brands": Brand,
    "components": Component,
    "operation-types": OperationType,
}


def catalog_model(slug: str) -> type | None:
    """Devuelve el modelo del maestro o `None` si el slug no existe."""
    return CATALOG_MODELS.get(slug)
