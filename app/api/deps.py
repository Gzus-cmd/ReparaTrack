"""Dependencias HTTP: sesión de base de datos, reloj y composición de servicios."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.repositories.catalog_registry import catalog_model
from app.db.repositories.catalog_repository import SqlCatalogRepository
from app.db.repositories.customer_repository import SqlCustomerRepository
from app.db.repositories.equipment_repository import SqlEquipmentRepository
from app.db.repositories.service_order_repository import SqlServiceOrderRepository
from app.domain.errors import NotFoundError
from app.services.catalog_service import CatalogService
from app.services.customer_service import CustomerService
from app.services.equipment_service import EquipmentService
from app.services.ports import Clock


class SystemClock:
    """Implementación de producción del puerto `Clock`."""

    def now(self) -> datetime:
        return datetime.now(UTC)


def get_session(request: Request) -> Iterator[Session]:
    """Entrega una sesión de la fábrica registrada en la app.

    La transacción se confirma al terminar la petición con éxito: los
    repositorios solo hacen `flush` (plan §1.1) y el `commit` vive aquí.
    """
    session_factory = request.app.state.session_factory
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_clock() -> Clock:
    """Entrega el reloj del sistema; los tests lo sobrescriben."""
    return SystemClock()


def build_catalog_service(catalog: str, session: Session) -> CatalogService:
    """Compone el servicio del maestro pedido o falla con `not_found`."""
    return CatalogService(_catalog_repository(catalog, session))


def build_customer_service(session: Session) -> CustomerService:
    """Compone el servicio de clientes sobre el repositorio SQL."""
    return CustomerService(SqlCustomerRepository(session))


def build_equipment_service(session: Session) -> EquipmentService:
    """Compone el servicio de equipos con sus maestros y el historial."""
    return EquipmentService(
        equipment_repository=SqlEquipmentRepository(session),
        device_types=_catalog_repository("device-types", session),
        brands=_catalog_repository("brands", session),
        service_orders=SqlServiceOrderRepository(session),
        customers=SqlCustomerRepository(session),
    )


def _catalog_repository(catalog: str, session: Session) -> SqlCatalogRepository:
    model = catalog_model(catalog)
    if model is None:
        raise NotFoundError("el catálogo", catalog)
    return SqlCatalogRepository(session, model)


SessionDep = Annotated[Session, Depends(get_session)]
ClockDep = Annotated[Clock, Depends(get_clock)]
