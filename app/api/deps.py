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
from app.db.repositories.state_history_repository import SqlStateHistoryRepository
from app.domain.errors import NotFoundError
from app.services.abandonment_service import AbandonmentService
from app.services.catalog_service import CatalogService
from app.services.customer_service import CustomerService
from app.services.dashboard_service import DashboardService
from app.services.equipment_service import EquipmentService
from app.services.ports import Clock
from app.services.service_detail_service import ServiceDetailService
from app.services.service_order_service import ServiceOrderService
from app.services.warranty_service import WarrantyService


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
    """Compone el servicio de clientes sobre el repositorio SQL y sus servicios."""
    return CustomerService(
        SqlCustomerRepository(session),
        service_orders=SqlServiceOrderRepository(session),
    )


def build_equipment_service(session: Session) -> EquipmentService:
    """Compone el servicio de equipos con sus maestros y el historial."""
    return EquipmentService(
        equipment_repository=SqlEquipmentRepository(session),
        device_types=_catalog_repository("device-types", session),
        brands=_catalog_repository("brands", session),
        operation_types=_catalog_repository("operation-types", session),
        components=_catalog_repository("components", session),
        service_orders=SqlServiceOrderRepository(session),
        state_history=SqlStateHistoryRepository(session),
        customers=SqlCustomerRepository(session),
    )


def build_service_order_service(session: Session, clock: Clock) -> ServiceOrderService:
    """Compone el servicio de órdenes con el reloj inyectado por la petición."""
    return ServiceOrderService(
        service_orders=SqlServiceOrderRepository(session),
        state_history=SqlStateHistoryRepository(session),
        customers=SqlCustomerRepository(session),
        equipments=SqlEquipmentRepository(session),
        equipment_service=build_equipment_service(session),
        clock=clock,
    )


def build_service_detail_service(session: Session) -> ServiceDetailService:
    """Compone el servicio de detalles con los maestros de operación y componente."""
    return ServiceDetailService(
        service_orders=SqlServiceOrderRepository(session),
        operation_types=_catalog_repository("operation-types", session),
        components=_catalog_repository("components", session),
    )


def build_dashboard_service(session: Session, clock: Clock) -> DashboardService:
    """Compone el tablero con el reloj inyectado por la petición."""
    return DashboardService(
        service_orders=SqlServiceOrderRepository(session),
        clock=clock,
    )


def build_warranty_service(session: Session, clock: Clock) -> WarrantyService:
    """Compone el servicio de garantía con el reloj inyectado por la petición."""
    return WarrantyService(
        service_orders=SqlServiceOrderRepository(session),
        clock=clock,
    )


def build_abandonment_service(session: Session, clock: Clock) -> AbandonmentService:
    """Compone el servicio de abandono con el reloj inyectado por la petición."""
    return AbandonmentService(
        service_orders=SqlServiceOrderRepository(session),
        clock=clock,
    )


def _catalog_repository(catalog: str, session: Session) -> SqlCatalogRepository:
    model = catalog_model(catalog)
    if model is None:
        raise NotFoundError("el catálogo", catalog)
    return SqlCatalogRepository(session, model)


SessionDep = Annotated[Session, Depends(get_session)]
ClockDep = Annotated[Clock, Depends(get_clock)]
