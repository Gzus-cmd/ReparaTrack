"""Servicio de equipos: alta con código correlativo, búsqueda e historial (RF-03, RF-08).

El correlativo lo entrega `EquipmentRepository` (T-15): el servicio no lo
reimplementa ni usa `MAX(id) + 1`. El historial técnico compone servicios,
líneas de detalle y bitácora de estados con consultas por lote, sin N+1. No
importa SQLAlchemy ni FastAPI.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.enums import ServiceStatus
from app.domain.errors import NotFoundError, ValidationError
from app.services.ports import (
    CatalogRepository,
    CatalogValue,
    CustomerRecord,
    CustomerRepository,
    EquipmentRecord,
    EquipmentRepository,
    ServiceDetailRecord,
    ServiceOrderRecord,
    ServiceOrderRepository,
    StateHistoryRecord,
    StateHistoryRepository,
)

EQUIPMENT_RESOURCE = "el equipo"

HISTORY_SECTIONS: frozenset[str] = frozenset({"details", "states"})


@dataclass(frozen=True, slots=True)
class CatalogReference:
    """Referencia mínima a un valor de maestro para la respuesta de la API."""

    id: int
    name: str


@dataclass(frozen=True, slots=True)
class CustomerReference:
    """Contacto mínimo del dueño vigente del equipo."""

    id: int
    name: str
    phone: str


@dataclass(frozen=True, slots=True)
class EquipmentView:
    """Equipo con sus referencias y el historial anticipado (RF-03)."""

    id: int
    internal_code: str
    device_type: CatalogReference
    brand: CatalogReference
    model: str
    serial_number: str | None
    created_at: datetime
    current_owner: CustomerReference | None
    previous_services_count: int


@dataclass(frozen=True, slots=True)
class HistoryDetail:
    """Línea de detalle dentro del historial técnico."""

    id: int
    operation_type: CatalogReference
    component: CatalogReference | None
    description: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class HistoryState:
    """Movimiento de la bitácora dentro del historial técnico."""

    id: int
    status: str
    status_label: str
    changed_at: datetime
    comment: str | None


@dataclass(frozen=True, slots=True)
class HistoryService:
    """Servicio previo del equipo con su cliente, estado y secciones pedidas."""

    id: int
    customer: CustomerReference
    status: str
    status_label: str
    received_at: datetime
    delivered_at: datetime | None
    reported_failure: str
    physical_condition: str
    accessories: str
    password_requested: bool
    origin_service_id: int | None
    states: tuple[HistoryState, ...] | None
    details: tuple[HistoryDetail, ...] | None


@dataclass(frozen=True, slots=True)
class EquipmentHistory:
    """Historial técnico completo de un equipo (RF-08)."""

    equipment: EquipmentView
    services: tuple[HistoryService, ...]


class EquipmentService:
    """Casos de uso del equipo sobre los puertos de persistencia."""

    def __init__(
        self,
        *,
        equipment_repository: EquipmentRepository,
        device_types: CatalogRepository,
        brands: CatalogRepository,
        operation_types: CatalogRepository,
        components: CatalogRepository,
        service_orders: ServiceOrderRepository,
        state_history: StateHistoryRepository,
        customers: CustomerRepository,
    ) -> None:
        self._equipment_repository = equipment_repository
        self._device_types = device_types
        self._brands = brands
        self._operation_types = operation_types
        self._components = components
        self._service_orders = service_orders
        self._state_history = state_history
        self._customers = customers

    def create(
        self,
        *,
        device_type_id: int,
        brand_id: int,
        model: str,
        serial_number: str | None = None,
    ) -> EquipmentView:
        """Valida los maestros activos y delega el alta con su correlativo."""
        device_type = self._active_catalog_value(
            self._device_types, device_type_id, "device_type_id", "El tipo de dispositivo"
        )
        brand = self._active_catalog_value(self._brands, brand_id, "brand_id", "La marca")
        display_model = " ".join(model.split())
        if not display_model:
            raise ValidationError("model", "El modelo del equipo no puede estar vacío.")
        display_serial = serial_number.strip() if serial_number else None
        record = self._equipment_repository.create(
            device_type_id=device_type_id,
            brand_id=brand_id,
            model=display_model,
            serial_number=display_serial or None,
        )
        return EquipmentView(
            id=record.id,
            internal_code=record.internal_code,
            device_type=CatalogReference(id=device_type.id, name=device_type.name),
            brand=CatalogReference(id=brand.id, name=brand.name),
            model=record.model,
            serial_number=record.serial_number,
            created_at=record.created_at,
            current_owner=None,
            previous_services_count=0,
        )

    def lookup(
        self, *, internal_code: str | None = None, serial_number: str | None = None
    ) -> EquipmentView:
        """Identifica el equipo por código o serial, con precedencia del código (D-06)."""
        code = (internal_code or "").strip()
        serial = (serial_number or "").strip()
        if not code and not serial:
            raise ValidationError(
                "internal_code",
                "Indique el código interno o el número de serie del equipo.",
            )
        if code:
            record = self._equipment_repository.find_by_internal_code(code)
            if record is None:
                raise NotFoundError(EQUIPMENT_RESOURCE, code)
        else:
            record = self._equipment_repository.find_by_serial_number(serial)
            if record is None:
                raise NotFoundError(EQUIPMENT_RESOURCE, serial)
        return self._view(record)

    def history(
        self,
        identifier: str | int,
        *,
        include: Iterable[str] | None = None,
    ) -> EquipmentHistory:
        """Historial técnico completo, consultable por id, código o serial.

        `include` filtra las secciones (`details`, `states`); omitir una sección
        la deja en `None`, de modo que el cliente distingue "no pedida" de
        "vacía". Los detalles se resuelven por lote y la bitácora por orden: el
        historial es de un solo equipo y no repite consultas por línea.
        """
        sections = _parse_sections(include)
        record = self._resolve(identifier)
        orders = self._service_orders.list_for_equipment(record.id)
        order_ids = [order.id for order in orders]

        if "states" in sections:
            states_by_order = {
                order_id: _states(self._state_history.list_for_order(order_id))
                for order_id in order_ids
            }
        else:
            states_by_order = dict.fromkeys(order_ids)
        if "details" in sections:
            grouped_details = self._details_by_order(order_ids)
            details_by_order = {
                order_id: grouped_details.get(order_id, ()) for order_id in order_ids
            }
        else:
            details_by_order = dict.fromkeys(order_ids)
        customers = {
            order.customer_id: customer
            for order in orders
            if (customer := self._customers.get(order.customer_id)) is not None
        }

        services: list[HistoryService] = []
        for order in orders:
            customer = customers.get(order.customer_id)
            if customer is None:  # pragma: no cover - defensa ante datos huérfanos
                raise NotFoundError("el cliente", order.customer_id)
            services.append(
                self._history_service(
                    order,
                    customer,
                    states_by_order[order.id],
                    details_by_order[order.id],
                )
            )
        return EquipmentHistory(equipment=self._view(record), services=tuple(services))

    # --- helpers -------------------------------------------------------------

    def _details_by_order(self, order_ids: Sequence[int]) -> dict[int, tuple[HistoryDetail, ...]]:
        """Líneas de todas las órdenes con los nombres de catálogo resueltos."""
        operation_names = {value.id: value.name for value in self._operation_types.list_all()}
        component_names = {value.id: value.name for value in self._components.list_all()}
        grouped: dict[int, list[HistoryDetail]] = {}
        for detail in self._service_orders.list_details_for_orders(order_ids):
            grouped.setdefault(detail.service_order_id, []).append(
                _history_detail(detail, operation_names, component_names)
            )
        return {order_id: tuple(items) for order_id, items in grouped.items()}

    def _history_service(
        self,
        order: ServiceOrderRecord,
        customer: CustomerRecord,
        states: tuple[HistoryState, ...] | None,
        details: tuple[HistoryDetail, ...] | None,
    ) -> HistoryService:
        status = ServiceStatus.parse(order.status)
        return HistoryService(
            id=order.id,
            customer=_customer_reference(customer),
            status=status.value,
            status_label=status.label,
            received_at=_as_utc(order.received_at),
            delivered_at=None if order.delivered_at is None else _as_utc(order.delivered_at),
            reported_failure=order.reported_failure,
            physical_condition=order.physical_condition,
            accessories=order.accessories,
            password_requested=order.password_requested,
            origin_service_id=order.origin_service_id,
            states=None if states is None else states,
            details=None if details is None else details,
        )

    def _resolve(self, identifier: str | int) -> EquipmentRecord:
        """Resuelve el equipo por id numérico, código interno o número de serie.

        El código interno tiene precedencia sobre el serial (D-06): es la
        identidad fuerte, mientras que el serial es opcional y puede repetirse.
        """
        if isinstance(identifier, bool):
            raise NotFoundError(EQUIPMENT_RESOURCE, identifier)
        if isinstance(identifier, int):
            record = self._equipment_repository.get(identifier)
            if record is None:
                raise NotFoundError(EQUIPMENT_RESOURCE, identifier)
            return record

        reference = identifier.strip()
        if reference.isdigit():
            record = self._equipment_repository.get(int(reference))
            if record is not None:
                return record
        record = self._equipment_repository.find_by_internal_code(reference)
        if record is None:
            record = self._equipment_repository.find_by_serial_number(reference)
        if record is None:
            raise NotFoundError(EQUIPMENT_RESOURCE, identifier)
        return record

    def _view(self, record: EquipmentRecord) -> EquipmentView:
        return EquipmentView(
            id=record.id,
            internal_code=record.internal_code,
            device_type=self._reference(self._device_types, record.device_type_id),
            brand=self._reference(self._brands, record.brand_id),
            model=record.model,
            serial_number=record.serial_number,
            created_at=record.created_at,
            current_owner=self._current_owner(record.id),
            previous_services_count=self._service_orders.count_for_equipment(record.id),
        )

    def _current_owner(self, equipment_id: int) -> CustomerReference | None:
        customer_id = self._service_orders.find_current_customer_id(equipment_id)
        if customer_id is None:
            return None
        customer = self._customers.get(customer_id)
        return None if customer is None else _customer_reference(customer)

    @staticmethod
    def _active_catalog_value(
        repository: CatalogRepository,
        catalog_id: int,
        field: str,
        label: str,
    ) -> CatalogValue:
        value = repository.get(catalog_id)
        if value is None or not value.is_active:
            raise ValidationError(field, f"{label} no existe o está inactivo.")
        return value

    @staticmethod
    def _reference(repository: CatalogRepository, catalog_id: int) -> CatalogReference:
        value = repository.get(catalog_id)
        return CatalogReference(id=catalog_id, name="" if value is None else value.name)


def _parse_sections(include: Iterable[str] | None) -> frozenset[str]:
    """Normaliza `include` y rechaza secciones desconocidas con `validation_error`."""
    if include is None:
        return HISTORY_SECTIONS
    requested = {part.strip().lower() for part in include if part and part.strip()}
    unknown = requested - HISTORY_SECTIONS
    if unknown:
        raise ValidationError(
            "include",
            "Secciones válidas del historial: details, states.",
        )
    return frozenset(requested) or HISTORY_SECTIONS


def _states(
    entries: Sequence[StateHistoryRecord],
) -> tuple[HistoryState, ...]:
    """Traduce la bitácora de una orden con su etiqueta en español."""
    return tuple(_history_state(entry) for entry in entries)


def _history_state(entry: StateHistoryRecord) -> HistoryState:
    status = ServiceStatus.parse(entry.status)
    return HistoryState(
        id=entry.id,
        status=status.value,
        status_label=status.label,
        changed_at=_as_utc(entry.changed_at),
        comment=entry.comment,
    )


def _history_detail(
    detail: ServiceDetailRecord,
    operation_names: dict[int, str],
    component_names: dict[int, str],
) -> HistoryDetail:
    component = (
        None
        if detail.component_id is None
        else CatalogReference(
            id=detail.component_id,
            name=component_names.get(detail.component_id, ""),
        )
    )
    return HistoryDetail(
        id=detail.id,
        operation_type=CatalogReference(
            id=detail.operation_type_id,
            name=operation_names.get(detail.operation_type_id, ""),
        ),
        component=component,
        description=detail.description,
        created_at=_as_utc(detail.created_at),
    )


def _customer_reference(customer: CustomerRecord) -> CustomerReference:
    return CustomerReference(id=customer.id, name=customer.name, phone=customer.phone)


def _as_utc(moment: datetime) -> datetime:
    """Reinterpreta como UTC una fecha sin zona (SQLite no conserva la zona)."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
