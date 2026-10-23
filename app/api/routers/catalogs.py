"""Router simétrico de los cuatro maestros (RF-01 / T-17)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import SessionDep, build_catalog_service
from app.api.schemas.catalogs import CatalogValueRead, CatalogValueWrite
from app.services.catalog_service import CatalogValueView

router = APIRouter(prefix="/catalogs", tags=["maestros"])

CATALOG_PATH = "/{catalog}"
VALUE_PATH = "/{catalog}/{catalog_id}"


def _to_read(value: CatalogValueView) -> CatalogValueRead:
    return CatalogValueRead(
        id=value.id,
        name=value.name,
        is_active=value.is_active,
        in_use=value.in_use,
    )


@router.get(
    CATALOG_PATH,
    response_model=list[CatalogValueRead],
    summary="Lista los valores de un maestro",
)
def list_values(catalog: str, session: SessionDep, active: bool = True) -> list[CatalogValueRead]:
    """Devuelve los valores activos; con `active=false` incluye los inactivos."""
    service = build_catalog_service(catalog, session)
    values = service.list_values(include_inactive=not active)
    return [_to_read(value) for value in values]


@router.get(VALUE_PATH, response_model=CatalogValueRead, summary="Obtiene un valor de maestro")
def get_value(catalog: str, catalog_id: int, session: SessionDep) -> CatalogValueRead:
    """Devuelve un valor concreto o `404`."""
    service = build_catalog_service(catalog, session)
    return _to_read(service.get_value(catalog_id))


@router.post(
    CATALOG_PATH,
    response_model=CatalogValueRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crea un valor de maestro",
)
def create_value(catalog: str, payload: CatalogValueWrite, session: SessionDep) -> CatalogValueRead:
    """Rechaza duplicados normalizados con `409 catalog_duplicate`."""
    service = build_catalog_service(catalog, session)
    return _to_read(service.create(payload.name))


@router.patch(VALUE_PATH, response_model=CatalogValueRead, summary="Renombra un valor de maestro")
def rename_value(
    catalog: str, catalog_id: int, payload: CatalogValueWrite, session: SessionDep
) -> CatalogValueRead:
    """Renombra validando duplicados con `409 catalog_duplicate`."""
    service = build_catalog_service(catalog, session)
    return _to_read(service.rename(catalog_id, payload.name))


@router.post(
    f"{VALUE_PATH}/deactivate",
    response_model=CatalogValueRead,
    summary="Da de baja lógica un valor de maestro",
)
def deactivate_value(catalog: str, catalog_id: int, session: SessionDep) -> CatalogValueRead:
    """Baja lógica idempotente: el valor deja de ofrecerse pero no se borra."""
    service = build_catalog_service(catalog, session)
    return _to_read(service.deactivate(catalog_id))


@router.post(
    f"{VALUE_PATH}/activate",
    response_model=CatalogValueRead,
    summary="Reactiva un valor de maestro",
)
def activate_value(catalog: str, catalog_id: int, session: SessionDep) -> CatalogValueRead:
    """Reactiva un valor previamente dado de baja."""
    service = build_catalog_service(catalog, session)
    return _to_read(service.activate(catalog_id))


@router.delete(
    VALUE_PATH,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borra un valor de maestro sin uso",
)
def delete_value(catalog: str, catalog_id: int, session: SessionDep) -> None:
    """Borra solo si no está en uso; si lo está responde `409 catalog_value_in_use`."""
    build_catalog_service(catalog, session).delete(catalog_id)
