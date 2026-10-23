"""Tablero "equipos en taller" (RF-07 / T-28).

Responde el dolor D1 con los servicios que siguen en taller: cliente, estado y
días transcurridos. La composición es de solo lectura y no duplica reglas: los
umbrales salen de `domain/rules.py` y el "ahora" del puerto `Clock`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain import rules
from app.domain.enums import ServiceStatus
from app.services.ports import Clock, OpenServiceOrderRecord, ServiceOrderRepository


@dataclass(frozen=True, slots=True)
class WorkbenchItem:
    """Fila del tablero con las métricas y la regla de umbral aplicable."""

    service_order_id: int
    customer_name: str
    equipment_internal_code: str
    device_type: str
    status: str
    status_label: str
    received_at: datetime
    days_since_reception: int
    days_in_status: int
    is_over_threshold: bool
    threshold_rule: str | None


@dataclass(frozen=True, slots=True)
class AlertGroup:
    """Servicios que ya cumplen una regla de abandono, agrupados por regla."""

    rule: str
    threshold_days: int
    service_order_ids: tuple[int, ...]

    @property
    def count(self) -> int:
        return len(self.service_order_ids)


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    """Conteo por estado y alertas de umbral separadas por regla (RF-07)."""

    by_status: dict[str, int]
    alerts: dict[str, AlertGroup]


class DashboardService:
    """Casos de uso del tablero sobre el repositorio de órdenes."""

    def __init__(self, *, service_orders: ServiceOrderRepository, clock: Clock) -> None:
        self._service_orders = service_orders
        self._clock = clock

    def workbench(self, *, status: str | None = None) -> list[WorkbenchItem]:
        """Equipos sin entregar, del más antiguo al más reciente por días."""
        selected = None if status is None else ServiceStatus.parse(status)
        now = self._clock.now()
        items = [
            self._item(record, now)
            for record in self._service_orders.list_open()
            if selected is None or record.status == selected.value
        ]
        return sorted(
            items,
            key=lambda item: (-item.days_since_reception, -item.service_order_id),
        )

    def summary(self) -> DashboardSummary:
        """Cuenta por estado y separa las alertas RN-07 de las RN-10.

        Las dos agregaciones son independientes: el conteo sale del repositorio
        y las alertas se evalúan con `rules.abandonment_eligibility`, la misma
        función que usan la transición y el tablero. Ningún umbral se recalcula
        aquí.
        """
        counts = self._service_orders.count_by_status()
        by_status = {status.value: int(counts.get(status.value, 0)) for status in ServiceStatus}

        now = self._clock.now()
        found: dict[str, list[int]] = {rule.code: [] for rule in rules.ABANDONMENT_RULES.values()}
        for record in self._service_orders.list_open():
            evaluation = rules.abandonment_eligibility(
                _as_utc(record.entered_at), now, record.status
            )
            if evaluation.eligible and evaluation.rule in found:
                found[evaluation.rule].append(record.id)

        alerts = {
            rule.code: AlertGroup(
                rule=rule.code,
                threshold_days=rule.required_days,
                service_order_ids=tuple(sorted(found[rule.code])),
            )
            for rule in rules.ABANDONMENT_RULES.values()
        }
        return DashboardSummary(by_status=by_status, alerts=alerts)

    def _item(self, record: OpenServiceOrderRecord, now: datetime) -> WorkbenchItem:
        status = ServiceStatus.parse(record.status)
        evaluation = rules.abandonment_eligibility(_as_utc(record.entered_at), now, status)
        return WorkbenchItem(
            service_order_id=record.id,
            customer_name=record.customer_name,
            equipment_internal_code=record.equipment_internal_code,
            device_type=record.device_type_name,
            status=status.value,
            status_label=status.label,
            received_at=_as_utc(record.received_at),
            days_since_reception=rules.days_between(record.received_at, now),
            days_in_status=evaluation.days_in_status,
            is_over_threshold=evaluation.eligible,
            threshold_rule=evaluation.rule,
        )


def _as_utc(moment: datetime) -> datetime:
    """Reinterpreta como UTC una fecha sin zona (SQLite no conserva la zona)."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
