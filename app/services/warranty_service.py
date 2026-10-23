"""Servicio de garantía: candidatos y elegibilidad (RF-09 / T-32).

El sistema **alerta** con los servicios del mismo equipo entregados dentro de
los 90 días; el técnico **decide** si es la misma falla (RN-04). No se compara
ni se bloquea por el texto de la falla reportada. Los umbrales salen de
`domain/rules.py` y el "ahora" del puerto `Clock`: aquí no se recalcula nada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain import rules
from app.domain.errors import NotFoundError
from app.services.ports import Clock, ServiceOrderRecord, ServiceOrderRepository

ORIGIN_RESOURCE = "la orden de servicio de origen"


@dataclass(frozen=True, slots=True)
class WarrantyCandidate:
    """Servicio entregado que todavía está dentro de la garantía."""

    service_order_id: int
    delivered_at: datetime
    days_since_delivery: int
    warranty_days_left: int
    reported_failure: str


@dataclass(frozen=True, slots=True)
class WarrantyEvaluation:
    """Resultado de evaluar un origen concreto para el endpoint de elegibilidad."""

    eligible: bool
    days_since_delivery: int | None
    reason: str


class WarrantyService:
    """Casos de uso de garantía sobre el repositorio de órdenes."""

    def __init__(self, *, service_orders: ServiceOrderRepository, clock: Clock) -> None:
        self._service_orders = service_orders
        self._clock = clock

    def candidates(
        self, *, equipment_id: int, as_of: datetime | None = None
    ) -> list[WarrantyCandidate]:
        """Servicios entregados hace menos de 90 días, del más reciente al más antiguo."""
        moment = as_of or self._clock.now()
        candidates: list[WarrantyCandidate] = []
        for order in self._service_orders.list_for_equipment(equipment_id):
            candidate = _candidate(order, moment)
            if candidate is not None:
                candidates.append(candidate)
        return sorted(
            candidates,
            key=lambda item: (item.delivered_at, item.service_order_id),
            reverse=True,
        )

    def eligibility(
        self, *, origin_service_id: int, as_of: datetime | None = None
    ) -> WarrantyEvaluation:
        """Evalúa un origen concreto; un origen inexistente responde `not_found`."""
        origin = self._service_orders.get(origin_service_id)
        if origin is None:
            raise NotFoundError(ORIGIN_RESOURCE, origin_service_id)
        evaluation = rules.warranty_eligibility(
            None if origin.delivered_at is None else _as_utc(origin.delivered_at),
            origin.status,
            as_of or self._clock.now(),
        )
        return WarrantyEvaluation(
            eligible=evaluation.eligible,
            days_since_delivery=evaluation.days_since_delivery,
            reason=evaluation.reason,
        )


def _candidate(order: ServiceOrderRecord, as_of: datetime) -> WarrantyCandidate | None:
    """Traduce una orden a candidato solo si el dominio la declara elegible."""
    if order.delivered_at is None:
        return None
    evaluation = rules.warranty_eligibility(_as_utc(order.delivered_at), order.status, as_of)
    if not evaluation.eligible or evaluation.days_since_delivery is None:
        return None
    return WarrantyCandidate(
        service_order_id=order.id,
        delivered_at=_as_utc(order.delivered_at),
        days_since_delivery=evaluation.days_since_delivery,
        warranty_days_left=evaluation.warranty_days_left,
        reported_failure=order.reported_failure,
    )


def _as_utc(moment: datetime) -> datetime:
    """Reinterpreta como UTC una fecha sin zona (SQLite no conserva la zona)."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
