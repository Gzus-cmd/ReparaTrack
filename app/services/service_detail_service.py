"""Servicio de líneas de detalle del servicio (RF-05 / RN-03).

Una línea es la evidencia del trabajo realizado: operación obligatoria,
componente opcional y descripción. En órdenes terminales no se agregan ni se
borran líneas (`service_order_terminal`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.enums import ServiceStatus
from app.domain.errors import NotFoundError, ServiceOrderTerminalError, ValidationError
from app.services.ports import (
    CatalogRepository,
    CatalogValue,
    ServiceDetailRecord,
    ServiceOrderRecord,
    ServiceOrderRepository,
)

SERVICE_ORDER_RESOURCE = "la orden de servicio"
DETAIL_RESOURCE = "la línea de detalle"


@dataclass(frozen=True, slots=True)
class CatalogReference:
    """Referencia mínima a un valor de maestro."""

    id: int
    name: str


@dataclass(frozen=True, slots=True)
class ServiceDetailView:
    """Línea de detalle con las referencias resueltas para la UI."""

    id: int
    service_order_id: int
    operation_type: CatalogReference
    component: CatalogReference | None
    description: str
    created_at: datetime


class ServiceDetailService:
    """Casos de uso de las líneas de detalle sobre los puertos de persistencia."""

    def __init__(
        self,
        *,
        service_orders: ServiceOrderRepository,
        operation_types: CatalogRepository,
        components: CatalogRepository,
    ) -> None:
        self._service_orders = service_orders
        self._operation_types = operation_types
        self._components = components

    def list(self, service_order_id: int) -> list[ServiceDetailView]:
        """Líneas registradas, en orden de carga."""
        self._order_or_404(service_order_id)
        return [
            self._view(detail) for detail in self._service_orders.list_details(service_order_id)
        ]

    def add(
        self,
        service_order_id: int,
        *,
        operation_type_id: int,
        description: str,
        component_id: int | None = None,
    ) -> ServiceDetailView:
        """Valida la operación, el componente opcional y el estado de la orden."""
        order = self._order_or_404(service_order_id)
        self._ensure_not_terminal(order)
        operation = self._active_value(
            self._operation_types, operation_type_id, "operation_type_id", "La operación"
        )
        component = None
        if component_id is not None:
            component = self._active_value(
                self._components, component_id, "component_id", "El componente"
            )
        normalized = " ".join(description.split())
        if not normalized:
            raise ValidationError("description", "La descripción de la línea es obligatoria.")
        detail = self._service_orders.add_detail(
            service_order_id=service_order_id,
            operation_type_id=operation.id,
            description=normalized,
            component_id=None if component is None else component.id,
        )
        return self._view(detail)

    def delete(self, service_order_id: int, detail_id: int) -> None:
        """Corrige una línea mal cargada; nunca en órdenes terminales."""
        order = self._order_or_404(service_order_id)
        self._ensure_not_terminal(order)
        if not self._service_orders.delete_detail(service_order_id, detail_id):
            raise NotFoundError(DETAIL_RESOURCE, detail_id)

    # --- helpers -------------------------------------------------------------

    def _order_or_404(self, service_order_id: int) -> ServiceOrderRecord:
        order = self._service_orders.get(service_order_id)
        if order is None:
            raise NotFoundError(SERVICE_ORDER_RESOURCE, service_order_id)
        return order

    @staticmethod
    def _ensure_not_terminal(order: ServiceOrderRecord) -> None:
        status = ServiceStatus.parse(order.status)
        if status.is_terminal:
            raise ServiceOrderTerminalError(order.id, status)

    @staticmethod
    def _active_value(
        repository: CatalogRepository,
        catalog_id: int,
        field: str,
        label: str,
    ) -> CatalogValue:
        value = repository.get(catalog_id)
        if value is None or not value.is_active:
            raise ValidationError(field, f"{label} no existe o está inactiva.")
        return value

    def _view(self, detail: ServiceDetailRecord) -> ServiceDetailView:
        operation = self._reference(self._operation_types, detail.operation_type_id)
        component = (
            None
            if detail.component_id is None
            else self._reference(self._components, detail.component_id)
        )
        return ServiceDetailView(
            id=detail.id,
            service_order_id=detail.service_order_id,
            operation_type=operation,
            component=component,
            description=detail.description,
            created_at=_as_utc(detail.created_at),
        )

    @staticmethod
    def _reference(repository: CatalogRepository, catalog_id: int) -> CatalogReference:
        value = repository.get(catalog_id)
        return CatalogReference(id=catalog_id, name="" if value is None else value.name)


def _as_utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
