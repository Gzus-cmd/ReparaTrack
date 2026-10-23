"""Puertos de la capa de aplicación: contratos que la persistencia implementa.

Los servicios dependen de estos protocolos y de los DTO de lectura, nunca de
SQLAlchemy ni de FastAPI (regla de dependencia del plan §1.1).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class CatalogValue:
    """Valor de un maestro (tipo de dispositivo, marca, componente u operación)."""

    id: int
    name: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class CustomerRecord:
    """Cliente con su contacto; nunca incluye contraseñas."""

    id: int
    name: str
    phone: str
    email: str | None
    document: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EquipmentRecord:
    """Equipo identificado por su código interno correlativo (RN-02)."""

    id: int
    internal_code: str
    device_type_id: int
    brand_id: int
    model: str
    serial_number: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ServiceOrderRecord:
    """Orden de servicio con su estado actual."""

    id: int
    equipment_id: int
    customer_id: int
    received_at: datetime
    reported_failure: str
    physical_condition: str
    accessories: str
    password_requested: bool
    status: str
    delivered_at: datetime | None
    origin_service_id: int | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ServiceDetailRecord:
    """Línea de detalle de un servicio."""

    id: int
    service_order_id: int
    operation_type_id: int
    component_id: int | None
    description: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StateHistoryRecord:
    """Fila append-only de la bitácora de estados."""

    id: int
    service_order_id: int
    status: str
    changed_at: datetime
    comment: str | None


@dataclass(frozen=True, slots=True)
class OpenServiceOrderRecord:
    """Orden sin entregar con los datos que el tablero muestra (RF-07).

    `entered_at` es la última fila del historial con el estado actual; si no
    existiera, cae en `received_at`. El repositorio lo resuelve en la misma
    consulta con joins, de modo que el tablero no incurre en N+1 (R-08).
    """

    id: int
    customer_name: str
    equipment_internal_code: str
    device_type_name: str
    status: str
    received_at: datetime
    entered_at: datetime


@dataclass(frozen=True, slots=True)
class CustomerServiceOrderRecord:
    """Resumen de un servicio para el historial del cliente (RF-08)."""

    id: int
    equipment_internal_code: str
    received_at: datetime
    delivered_at: datetime | None
    status: str
    reported_failure: str
    origin_service_id: int | None


@runtime_checkable
class Clock(Protocol):
    """Puerto del reloj: toda fecha "ahora" entra por aquí."""

    def now(self) -> datetime: ...


@runtime_checkable
class CatalogRepository(Protocol):
    """Repositorio genérico de los cuatro maestros (RF-01)."""

    def add(self, name: str) -> CatalogValue: ...

    def get(self, catalog_id: int) -> CatalogValue | None: ...

    def list_active(self) -> list[CatalogValue]: ...

    def list_all(self) -> list[CatalogValue]: ...

    def find_by_normalized_name(self, name: str) -> CatalogValue | None: ...

    def count_usages(self, catalog_id: int) -> int: ...

    def rename(self, catalog_id: int, name: str) -> CatalogValue | None: ...

    def set_active(self, catalog_id: int, *, is_active: bool) -> CatalogValue | None: ...

    def delete(self, catalog_id: int) -> bool: ...


@runtime_checkable
class CustomerRepository(Protocol):
    """Repositorio de clientes (RF-02)."""

    def add(
        self,
        *,
        name: str,
        phone: str,
        email: str | None = None,
        document: str | None = None,
    ) -> CustomerRecord: ...

    def get(self, customer_id: int) -> CustomerRecord | None: ...

    def find_by_document(self, document: str) -> CustomerRecord | None: ...

    def search(self, query: str, *, limit: int = 50, offset: int = 0) -> list[CustomerRecord]: ...

    def count(self, query: str = "") -> int: ...

    def update_contact(
        self, customer_id: int, changes: Mapping[str, Any]
    ) -> CustomerRecord | None: ...


@runtime_checkable
class EquipmentRepository(Protocol):
    """Repositorio de equipos con asignación atómica del código (RN-02)."""

    def create(
        self,
        *,
        device_type_id: int,
        brand_id: int,
        model: str,
        serial_number: str | None = None,
    ) -> EquipmentRecord: ...

    def get(self, equipment_id: int) -> EquipmentRecord | None: ...

    def find_by_internal_code(self, internal_code: str) -> EquipmentRecord | None: ...

    def find_by_serial_number(self, serial_number: str) -> EquipmentRecord | None: ...

    def list_all(self, *, limit: int = 50, offset: int = 0) -> list[EquipmentRecord]: ...

    def count(self) -> int: ...


@runtime_checkable
class ServiceOrderRepository(Protocol):
    """Repositorio de órdenes de servicio y sus detalles (RF-04, RF-05)."""

    def add(
        self,
        *,
        equipment_id: int,
        customer_id: int,
        received_at: datetime,
        reported_failure: str,
        physical_condition: str,
        accessories: str,
        password_requested: bool = False,
        status: str = "RECEIVED",
        delivered_at: datetime | None = None,
        origin_service_id: int | None = None,
    ) -> ServiceOrderRecord: ...

    def get(self, service_order_id: int) -> ServiceOrderRecord | None: ...

    def list(
        self,
        *,
        status: str | None = None,
        customer_id: int | None = None,
        equipment_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ServiceOrderRecord]: ...

    def count(
        self,
        *,
        status: str | None = None,
        customer_id: int | None = None,
        equipment_id: int | None = None,
    ) -> int: ...

    def update_status(
        self,
        service_order_id: int,
        *,
        status: str,
        delivered_at: datetime | None = None,
    ) -> ServiceOrderRecord | None: ...

    def add_detail(
        self,
        *,
        service_order_id: int,
        operation_type_id: int,
        description: str,
        component_id: int | None = None,
    ) -> ServiceDetailRecord: ...

    def list_details(self, service_order_id: int) -> Sequence[ServiceDetailRecord]: ...

    def get_detail(self, service_order_id: int, detail_id: int) -> ServiceDetailRecord | None: ...

    def delete_detail(self, service_order_id: int, detail_id: int) -> bool: ...

    def count_details(self, service_order_id: int) -> int: ...

    def count_for_equipment(self, equipment_id: int) -> int: ...

    def find_current_customer_id(self, equipment_id: int) -> int | None: ...

    def list_open(self) -> Sequence[OpenServiceOrderRecord]: ...

    def count_by_status(self) -> Mapping[str, int]: ...

    def list_for_equipment(self, equipment_id: int) -> Sequence[ServiceOrderRecord]: ...

    def find_by_origin(self, origin_service_id: int) -> ServiceOrderRecord | None: ...

    def list_for_customer(
        self,
        customer_id: int,
        *,
        received_from: datetime | None = None,
        received_to: datetime | None = None,
    ) -> Sequence[CustomerServiceOrderRecord]: ...

    def list_details_for_orders(
        self, service_order_ids: Sequence[int]
    ) -> Sequence[ServiceDetailRecord]: ...


@runtime_checkable
class StateHistoryRepository(Protocol):
    """Bitácora append-only: solo alta y lectura (RN-05)."""

    def add(
        self,
        *,
        service_order_id: int,
        status: str,
        changed_at: datetime,
        comment: str | None = None,
    ) -> StateHistoryRecord: ...

    def list_for_order(self, service_order_id: int) -> Sequence[StateHistoryRecord]: ...
