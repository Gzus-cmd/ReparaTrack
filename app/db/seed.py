"""Semilla idempotente de los maestros base (T-11).

"Diagnóstico" entra como dato sembrado, no como rama de código (D-09): así el
flujo de rechazo se cierra con una operación real y administrable.
"""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.catalog import Brand, Component, DeviceType, OperationType
from app.db.normalization import normalize_name

DEVICE_TYPE_NAMES = ("Laptop", "PC", "Impresora")
BRAND_NAMES = ("HP", "Dell", "Lenovo", "Asus", "Acer", "Apple")
COMPONENT_NAMES = (
    "RAM",
    "Disco",
    "Pasta térmica",
    "Pad térmico",
    "Batería",
    "Teclado",
)
OPERATION_TYPE_NAMES = (
    "Mantenimiento",
    "Reparación",
    "Diagnóstico",
    "Cambio",
    "Formateo",
    "Migración",
)

CATALOG_SEED: Mapping[str, tuple[type, tuple[str, ...]]] = {
    "device_types": (DeviceType, DEVICE_TYPE_NAMES),
    "brands": (Brand, BRAND_NAMES),
    "components": (Component, COMPONENT_NAMES),
    "operation_types": (OperationType, OPERATION_TYPE_NAMES),
}


def seed_catalogs(session: Session) -> dict[str, int]:
    """Inserta los valores base que falten y devuelve cuántos creó por maestro."""
    created: dict[str, int] = {}
    for key, (model, names) in CATALOG_SEED.items():
        existing = {normalize_name(name) for name in session.scalars(select(model.name))}
        new_values: list[str] = []
        for name in names:
            normalized = normalize_name(name)
            if normalized in existing:
                continue
            existing.add(normalized)
            new_values.append(name)
        for name in new_values:
            session.add(model(name=name))
        created[key] = len(new_values)
    session.flush()
    return created
