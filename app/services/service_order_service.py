"""Servicio de órdenes de servicio: recepción, transiciones y lectura (RF-04, RF-06).

Orquesta el dominio puro (matriz y reglas) dentro de una transacción; nunca
consulta el reloj del sistema (el puerto `Clock` entra por constructor) ni
importa SQLAlchemy o FastAPI (plan §1.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain import rules, state_machine
from app.domain.enums import ServiceStatus
from app.domain.errors import (
    EquipmentSourceInvalidError,
    NotFoundError,
    OriginAlreadyLinkedError,
    OriginNotDeliveredError,
    ValidationError,
    WarrantyEquipmentMismatchError,
    WarrantyExpiredError,
)
from app.services.equipment_service import EquipmentService
from app.services.ports import (
    Clock,
    CustomerRecord,
    CustomerRepository,
    EquipmentRecord,
    EquipmentRepository,
    ServiceOrderRecord,
    ServiceOrderRepository,
    StateHistoryRepository,
)

SERVICE_ORDER_RESOURCE = "la orden de servicio"
ORIGIN_RESOURCE = "la orden de servicio de origen"


@dataclass(frozen=True, slots=True)
class NewEquipment:
    """Datos mínimos para crear un equipo durante la recepción."""

    device_type_id: int
    brand_id: int
    model: str
    serial_number: str | None = None


@dataclass(frozen=True, slots=True)
class EquipmentReference:
    """Referencia mínima al equipo de la orden."""

    id: int
    internal_code: str
    model: str


@dataclass(frozen=True, slots=True)
class CustomerReference:
    """Contacto mínimo del cliente de la orden."""

    id: int
    name: str
    phone: str


@dataclass(frozen=True, slots=True)
class TransitionOption:
    """Destino alcanzable con el motivo de bloqueo, si lo tiene."""

    to_status: str
    status_label: str
    blocked_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ServiceOrderView:
    """Orden de servicio con sus métricas y transiciones permitidas."""

    id: int
    equipment: EquipmentReference
    customer: CustomerReference
    received_at: datetime
    delivered_at: datetime | None
    reported_failure: str
    physical_condition: str
    accessories: str
    password_requested: bool
    status: str
    status_label: str
    days_in_status: int
    days_since_reception: int
    details_count: int
    origin_service_id: int | None
    transitions: tuple[TransitionOption, ...]


@dataclass(frozen=True, slots=True)
class StateHistoryView:
    """Fila de la bitácora con su etiqueta en español."""

    id: int
    status: str
    status_label: str
    changed_at: datetime
    comment: str | None


@dataclass(frozen=True, slots=True)
class ServiceOrderPage:
    """Página de la bandeja con el total de coincidencias."""

    items: list[ServiceOrderView]
    total: int


def _normalize_text(value: str) -> str:
    """Colapsa espacios y recorta, sin cambiar el contenido del texto."""
    return " ".join(value.split())


def _normalize_comment(comment: str | None) -> str | None:
    """Un comentario en blanco equivale a no enviarlo."""
    if comment is None:
        return None
    normalized = _normalize_text(comment)
    return normalized or None


def _as_utc(moment: datetime) -> datetime:
    """Reinterpreta como UTC una fecha sin zona (SQLite no conserva la zona)."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


class ServiceOrderService:
    """Casos de uso de la orden de servicio sobre los puertos de persistencia."""

    def __init__(
        self,
        *,
        service_orders: ServiceOrderRepository,
        state_history: StateHistoryRepository,
        customers: CustomerRepository,
        equipments: EquipmentRepository,
        equipment_service: EquipmentService,
        clock: Clock,
    ) -> None:
        self._service_orders = service_orders
        self._state_history = state_history
        self._customers = customers
        self._equipments = equipments
        self._equipment_service = equipment_service
        self._clock = clock

    # --- RF-04: recepción -----------------------------------------------------

    def create(
        self,
        *,
        customer_id: int,
        reported_failure: str,
        accessories: str,
        physical_condition: str,
        equipment_id: int | None = None,
        new_equipment: NewEquipment | None = None,
        password_requested: bool = False,
        origin_service_id: int | None = None,
    ) -> ServiceOrderView:
        """Valida todo y recién después escribe la orden con su fila inicial.

        El vínculo de garantía (RF-09) se valida aquí, dentro de la misma
        transacción y antes de cualquier escritura: el sistema alerta y el
        técnico decide (RN-04).
        """
        if (equipment_id is None) == (new_equipment is None):
            raise EquipmentSourceInvalidError()

        failure = _normalize_text(reported_failure)
        if not failure:
            raise ValidationError("reported_failure", "La falla reportada es obligatoria.")
        received_accessories = _normalize_text(accessories)
        if not received_accessories:
            raise ValidationError("accessories", "Los accesorios son obligatorios.")
        condition = _normalize_text(physical_condition)
        if not condition:
            raise ValidationError("physical_condition", "La condición física es obligatoria.")

        if self._customers.get(customer_id) is None:
            raise ValidationError("customer_id", "El cliente indicado no existe.")

        now = self._clock.now()
        origin = (
            None if origin_service_id is None else self._warranty_origin(origin_service_id, now)
        )
        if equipment_id is not None:
            self._require_equipment(equipment_id)
            if origin is not None:
                self._ensure_origin_equipment(origin, equipment_id)
        else:
            if origin is not None:
                # Un equipo nuevo nunca puede ser el origen de garantía (RN-01).
                raise WarrantyEquipmentMismatchError(
                    origin_service_id=origin.id,
                    origin_equipment_id=origin.equipment_id,
                )
            assert new_equipment is not None  # garantizado por el XOR
            created_equipment = self._equipment_service.create(
                device_type_id=new_equipment.device_type_id,
                brand_id=new_equipment.brand_id,
                model=new_equipment.model,
                serial_number=new_equipment.serial_number,
            )
            equipment_id = created_equipment.id

        order = self._service_orders.add(
            equipment_id=equipment_id,
            customer_id=customer_id,
            received_at=now,
            reported_failure=failure,
            physical_condition=condition,
            accessories=received_accessories,
            password_requested=password_requested,
            status=ServiceStatus.RECEIVED.value,
            origin_service_id=origin_service_id,
        )
        self._state_history.add(
            service_order_id=order.id,
            status=ServiceStatus.RECEIVED.value,
            changed_at=now,
            comment="Recepción del equipo",
        )
        return self._view(order)

    # --- lectura -------------------------------------------------------------

    def get(self, service_order_id: int) -> ServiceOrderView:
        """Devuelve la ficha de la orden o `not_found`."""
        return self._view(self._order_or_404(service_order_id))

    def list(
        self,
        *,
        status: str | None = None,
        customer_id: int | None = None,
        equipment_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ServiceOrderPage:
        """Bandeja filtrable; valida el estado antes de tocar la base."""
        if status is not None:
            ServiceStatus.parse(status)
        records = self._service_orders.list(
            status=status,
            customer_id=customer_id,
            equipment_id=equipment_id,
            limit=limit,
            offset=offset,
        )
        total = self._service_orders.count(
            status=status, customer_id=customer_id, equipment_id=equipment_id
        )
        return ServiceOrderPage(items=[self._view(order) for order in records], total=total)

    # --- RF-06: transición de estado -----------------------------------------

    def transition(
        self,
        service_order_id: int,
        *,
        target: str,
        comment: str | None = None,
        confirm: bool = False,
    ) -> ServiceOrderView:
        """Valida la arista y persiste estado más una única fila de historial.

        Todas las guardas se evalúan antes de la primera escritura: un rechazo
        deja el estado y el conteo de historial intactos (RF-06).
        """
        order = self._order_or_404(service_order_id)
        current = ServiceStatus.parse(order.status)
        destination = ServiceStatus.parse(target)
        state_machine.assert_transition(current, destination)

        now = self._clock.now()
        self._ensure_guards(order, current, destination, now, confirm)

        updated = self._service_orders.update_status(
            service_order_id,
            status=destination.value,
            delivered_at=now if destination is ServiceStatus.DELIVERED else order.delivered_at,
        )
        if updated is None:  # pragma: no cover - la orden se acaba de leer
            raise NotFoundError(SERVICE_ORDER_RESOURCE, service_order_id)
        self._state_history.add(
            service_order_id=service_order_id,
            status=destination.value,
            changed_at=now,
            comment=_normalize_comment(comment),
        )
        return self._view(updated)

    def history(self, service_order_id: int) -> list[StateHistoryView]:
        """Bitácora inmutable ordenada por fecha y hora."""
        self._order_or_404(service_order_id)
        return [
            StateHistoryView(
                id=entry.id,
                status=entry.status,
                status_label=ServiceStatus.parse(entry.status).label,
                changed_at=_as_utc(entry.changed_at),
                comment=entry.comment,
            )
            for entry in self._state_history.list_for_order(service_order_id)
        ]

    # --- helpers -------------------------------------------------------------

    def _order_or_404(self, service_order_id: int) -> ServiceOrderRecord:
        order = self._service_orders.get(service_order_id)
        if order is None:
            raise NotFoundError(SERVICE_ORDER_RESOURCE, service_order_id)
        return order

    def _ensure_guards(
        self,
        order: ServiceOrderRecord,
        current: ServiceStatus,
        destination: ServiceStatus,
        now: datetime,
        confirm: bool,
    ) -> None:
        """Aplica las guardas de dominio antes de escribir cualquier fila."""
        if destination is ServiceStatus.READY_FOR_PICKUP:
            rules.ensure_details_for_pickup(
                self._service_orders.count_details(order.id), destination
            )
        if destination is ServiceStatus.ABANDONED:
            rules.ensure_abandonment_allowed(
                self._entered_at(order, current),
                now,
                current,
                confirm=confirm,
            )

    def _require_equipment(self, equipment_id: int) -> EquipmentRecord:
        equipment = self._equipments.get(equipment_id)
        if equipment is None:
            raise ValidationError("equipment_id", "El equipo indicado no existe.")
        return equipment

    def _warranty_origin(self, origin_service_id: int, now: datetime) -> ServiceOrderRecord:
        """Valida el origen de garantía antes de escribir cualquier fila (RF-09)."""
        origin = self._service_orders.get(origin_service_id)
        if origin is None:
            raise NotFoundError(ORIGIN_RESOURCE, origin_service_id)
        status = ServiceStatus.parse(origin.status)
        if status is not ServiceStatus.DELIVERED:
            raise OriginNotDeliveredError(origin_service_id, status)
        evaluation = rules.warranty_eligibility(
            None if origin.delivered_at is None else _as_utc(origin.delivered_at),
            status,
            now,
        )
        if not evaluation.eligible:
            raise WarrantyExpiredError(
                origin_service_id,
                evaluation.days_since_delivery or 0,
                rules.WARRANTY_DAYS,
            )
        linked = self._service_orders.find_by_origin(origin_service_id)
        if linked is not None:
            raise OriginAlreadyLinkedError(origin_service_id, linked.id)
        return origin

    @staticmethod
    def _ensure_origin_equipment(origin: ServiceOrderRecord, equipment_id: int) -> None:
        """RN-01: el reingreso vinculado pertenece al mismo equipo que el origen."""
        if origin.equipment_id != equipment_id:
            raise WarrantyEquipmentMismatchError(
                origin_service_id=origin.id,
                origin_equipment_id=origin.equipment_id,
                equipment_id=equipment_id,
            )

    def _view(self, order: ServiceOrderRecord) -> ServiceOrderView:
        equipment = self._require_equipment(order.equipment_id)
        customer = self._customers.get(order.customer_id)
        if customer is None:  # pragma: no cover - defensa ante datos huérfanos
            raise NotFoundError("el cliente", order.customer_id)

        now = self._clock.now()
        status = ServiceStatus.parse(order.status)
        details_count = self._service_orders.count_details(order.id)
        entered_at = self._entered_at(order, status)
        return ServiceOrderView(
            id=order.id,
            equipment=EquipmentReference(
                id=equipment.id,
                internal_code=equipment.internal_code,
                model=equipment.model,
            ),
            customer=_customer_reference(customer),
            received_at=_as_utc(order.received_at),
            delivered_at=None if order.delivered_at is None else _as_utc(order.delivered_at),
            reported_failure=order.reported_failure,
            physical_condition=order.physical_condition,
            accessories=order.accessories,
            password_requested=order.password_requested,
            status=status.value,
            status_label=status.label,
            days_in_status=rules.days_between(entered_at, now),
            days_since_reception=rules.days_between(order.received_at, now),
            details_count=details_count,
            origin_service_id=order.origin_service_id,
            transitions=self._transition_options(status, details_count, entered_at, now),
        )

    def _entered_at(self, order: ServiceOrderRecord, status: ServiceStatus) -> datetime:
        """Fecha de entrada al estado actual: última fila del historial con ese estado."""
        entries = [
            entry.changed_at
            for entry in self._state_history.list_for_order(order.id)
            if entry.status == status.value
        ]
        return max(entries) if entries else order.received_at

    def _transition_options(
        self,
        status: ServiceStatus,
        details_count: int,
        entered_at: datetime,
        now: datetime,
    ) -> tuple[TransitionOption, ...]:
        targets = sorted(state_machine.allowed_targets(status), key=list(ServiceStatus).index)
        return tuple(
            TransitionOption(
                to_status=target.value,
                status_label=target.label,
                blocked_reason=self._blocked_reason(status, target, details_count, entered_at, now),
            )
            for target in targets
        )

    @staticmethod
    def _blocked_reason(
        current: ServiceStatus,
        target: ServiceStatus,
        details_count: int,
        entered_at: datetime,
        now: datetime,
    ) -> str | None:
        """Motivo estable que la UI usa para deshabilitar un botón."""
        if target is ServiceStatus.READY_FOR_PICKUP and details_count < 1:
            return "details_required"
        if target is ServiceStatus.ABANDONED:
            evaluation = rules.abandonment_eligibility(entered_at, now, current)
            if evaluation.rule is not None and not evaluation.eligible:
                return "threshold_not_reached"
        return None


def _customer_reference(customer: CustomerRecord) -> CustomerReference:
    return CustomerReference(id=customer.id, name=customer.name, phone=customer.phone)
