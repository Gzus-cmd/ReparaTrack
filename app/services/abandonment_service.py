"""Servicio de abandono: candidatos por regla (RF-10 / T-34).

Dos grupos excluyentes por construcción: `AWAITING_APPROVAL` con 30 días o más
(RN-10) y `READY_FOR_PICKUP` con más de 180 días (RN-07). La elegibilidad la
decide `domain/rules.py`; este servicio solo reúne y ordena los candidatos. La
transición a `ABANDONED` sigue siendo manual y confirmada (riesgo D-07).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain import rules
from app.domain.enums import ServiceStatus
from app.domain.errors import ValidationError
from app.services.ports import Clock, OpenServiceOrderRecord, ServiceOrderRepository

RULE_FIELD = "rule"
RULE_CODES: tuple[str, ...] = tuple(rule.code for rule in rules.ABANDONMENT_RULES.values())
_RULE_ORDER: dict[str, int] = {code: index for index, code in enumerate(RULE_CODES)}


@dataclass(frozen=True, slots=True)
class AbandonmentCandidate:
    """Servicio que ya cumple el umbral de una regla de abandono."""

    service_order_id: int
    status: str
    days_in_status: int
    threshold_days: int
    rule: str
    customer_name: str
    equipment_internal_code: str


class AbandonmentService:
    """Casos de uso de abandono sobre el tablero de órdenes abiertas."""

    def __init__(self, *, service_orders: ServiceOrderRepository, clock: Clock) -> None:
        self._service_orders = service_orders
        self._clock = clock

    def candidates(self, *, rule: str | None = None) -> list[AbandonmentCandidate]:
        """Candidatos del grupo pedido; sin filtro devuelve ambos, siempre separados."""
        if rule is not None and rule not in _RULE_ORDER:
            raise ValidationError(
                RULE_FIELD,
                "La regla debe ser RN-07 o RN-10.",
            )
        now = self._clock.now()
        found = [
            candidate
            for record in self._service_orders.list_open()
            if (candidate := _candidate(record, now)) is not None
            and (rule is None or candidate.rule == rule)
        ]
        return sorted(
            found,
            key=lambda item: (
                _RULE_ORDER[item.rule],
                -item.days_in_status,
                item.service_order_id,
            ),
        )


def _candidate(record: OpenServiceOrderRecord, as_of: datetime) -> AbandonmentCandidate | None:
    """Traduce una orden abierta a candidato solo si el dominio la declara elegible."""
    evaluation = rules.abandonment_eligibility(_as_utc(record.entered_at), as_of, record.status)
    if not evaluation.eligible or evaluation.rule is None:
        return None
    return AbandonmentCandidate(
        service_order_id=record.id,
        status=ServiceStatus.parse(record.status).value,
        days_in_status=evaluation.days_in_status,
        threshold_days=evaluation.required_days or 0,
        rule=evaluation.rule,
        customer_name=record.customer_name,
        equipment_internal_code=record.equipment_internal_code,
    )


def _as_utc(moment: datetime) -> datetime:
    """Reinterpreta como UTC una fecha sin zona (SQLite no conserva la zona)."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
