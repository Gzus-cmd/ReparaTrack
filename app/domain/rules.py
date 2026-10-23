"""Reglas de negocio puras: umbrales temporales, detalle mínimo y abandono.

Todas las funciones reciben el instante de evaluación (`as_of`) de forma
explícita: el dominio nunca consulta el reloj del sistema. Los días se
calculan sobre la fecha calendario de negocio en `America/Lima`, aunque las
fechas se persistan en UTC (decisión D-04).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.domain.enums import ServiceStatus
from app.domain.errors import (
    ConfirmationRequiredError,
    DetailsRequiredError,
    ImmutableFieldError,
    InvalidTransitionError,
    ThresholdNotReachedError,
)
from app.domain.state_machine import allowed_targets

BUSINESS_TIMEZONE = ZoneInfo("America/Lima")

WARRANTY_DAYS = 90
APPROVAL_ABANDONMENT_DAYS = 30
PICKUP_ABANDONMENT_DAYS = 180

RN_APPROVAL_ABANDONMENT = "RN-10"
RN_PICKUP_ABANDONMENT = "RN-07"


def _as_status(status: ServiceStatus | str) -> ServiceStatus:
    """Normaliza la clave de estado recibida."""
    return status if isinstance(status, ServiceStatus) else ServiceStatus.parse(status)


# --- Base temporal (T-04) -----------------------------------------------------


def business_date(moment: datetime) -> date:
    """Fecha calendario de negocio en `America/Lima`.

    Un `datetime` sin zona se interpreta como UTC, porque SQLite no conserva
    la zona horaria al leer (riesgo R-05).
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(BUSINESS_TIMEZONE).date()


def days_between(start: datetime, as_of: datetime) -> int:
    """Días calendario de negocio transcurridos entre dos instantes."""
    return (business_date(as_of) - business_date(start)).days


# --- RN-03: detalle mínimo para listo para entrega (T-05) ---------------------


def ensure_details_for_pickup(details_count: int, target: ServiceStatus | str) -> None:
    """Impide `READY_FOR_PICKUP` sin al menos una línea de detalle.

    Solo actúa cuando el destino es `READY_FOR_PICKUP`; una línea con la
    operación "Diagnóstico" cuenta igual que cualquier otra, porque la regla
    no inspecciona el tipo de operación ni el texto de la descripción.
    """
    destination = _as_status(target)
    if destination is not ServiceStatus.READY_FOR_PICKUP:
        return
    if details_count < 1:
        raise DetailsRequiredError(details_count=details_count)


# --- RN-04: garantía de 90 días (T-06) ---------------------------------------


@dataclass(frozen=True, slots=True)
class WarrantyEligibility:
    """Resultado de evaluar la garantía de un servicio de origen."""

    eligible: bool
    days_since_delivery: int | None
    warranty_days_left: int
    reason: str


def warranty_eligibility(
    delivered_at: datetime | None,
    status: ServiceStatus | str,
    as_of: datetime,
) -> WarrantyEligibility:
    """Evalúa si un servicio entregado sigue dentro de la garantía.

    El sistema solo alerta: la decisión de vincular el reingreso sigue siendo
    del técnico (RN-04). No compara textos de falla.
    """
    origin_status = _as_status(status)
    if delivered_at is None or origin_status is not ServiceStatus.DELIVERED:
        return WarrantyEligibility(
            eligible=False,
            days_since_delivery=None,
            warranty_days_left=0,
            reason="origin_not_delivered",
        )

    elapsed = days_between(delivered_at, as_of)
    if elapsed < WARRANTY_DAYS:
        return WarrantyEligibility(
            eligible=True,
            days_since_delivery=elapsed,
            warranty_days_left=WARRANTY_DAYS - elapsed,
            reason="within_warranty",
        )

    return WarrantyEligibility(
        eligible=False,
        days_since_delivery=elapsed,
        warranty_days_left=0,
        reason="warranty_expired",
    )


# --- RN-07 / RN-10: abandono (T-07, T-08) ------------------------------------


@dataclass(frozen=True, slots=True)
class AbandonmentRule:
    """Regla de abandono asociada a un estado, con su comparación exacta."""

    code: str
    required_days: int
    inclusive: bool


ABANDONMENT_RULES: dict[ServiceStatus, AbandonmentRule] = {
    ServiceStatus.AWAITING_APPROVAL: AbandonmentRule(
        code=RN_APPROVAL_ABANDONMENT,
        required_days=APPROVAL_ABANDONMENT_DAYS,
        inclusive=True,
    ),
    ServiceStatus.READY_FOR_PICKUP: AbandonmentRule(
        code=RN_PICKUP_ABANDONMENT,
        required_days=PICKUP_ABANDONMENT_DAYS,
        inclusive=False,
    ),
}


@dataclass(frozen=True, slots=True)
class AbandonmentEligibility:
    """Resultado de evaluar si un servicio puede marcarse `ABANDONED`."""

    status: ServiceStatus
    rule: str | None
    days_in_status: int
    required_days: int | None
    eligible: bool
    reason: str


def abandonment_eligibility(
    entered_at: datetime,
    as_of: datetime,
    status: ServiceStatus | str,
) -> AbandonmentEligibility:
    """Evalúa el umbral de abandono sin lanzar errores.

    Asimetría deliberada (D-03): RN-10 habilita desde el día 30 inclusive
    (`>= 30`), RN-07 recién después del día 180 (`> 180`).
    """
    current = _as_status(status)
    days_in_status = days_between(entered_at, as_of)
    rule = ABANDONMENT_RULES.get(current)

    if rule is None:
        return AbandonmentEligibility(
            status=current,
            rule=None,
            days_in_status=days_in_status,
            required_days=None,
            eligible=False,
            reason="rule_not_applicable",
        )

    reached = (
        days_in_status >= rule.required_days
        if rule.inclusive
        else days_in_status > rule.required_days
    )
    return AbandonmentEligibility(
        status=current,
        rule=rule.code,
        days_in_status=days_in_status,
        required_days=rule.required_days,
        eligible=reached,
        reason="threshold_reached" if reached else "threshold_not_reached",
    )


def ensure_abandonment_allowed(
    entered_at: datetime,
    as_of: datetime,
    status: ServiceStatus | str,
    *,
    confirm: bool = False,
) -> AbandonmentEligibility:
    """Valida umbral y confirmación antes de marcar `ABANDONED`.

    El estado de origen debe ser alcanzable hacia `ABANDONED` según la matriz;
    el umbral se evalúa antes que la confirmación, para que el error más
    específico (`threshold_not_reached`) gane cuando fallan ambos.
    """
    current = _as_status(status)
    evaluation = abandonment_eligibility(entered_at, as_of, current)

    if evaluation.rule is None:
        raise InvalidTransitionError(
            current,
            ServiceStatus.ABANDONED,
            allowed_targets(current),
        )
    if not evaluation.eligible:
        raise ThresholdNotReachedError(
            rule=evaluation.rule,
            days_in_status=evaluation.days_in_status,
            required_days=evaluation.required_days or 0,
        )
    if not confirm:
        raise ConfirmationRequiredError(to_status=ServiceStatus.ABANDONED)

    return evaluation


# --- RN-08: evidencia de recepción inmutable (T-25) --------------------------


def assert_condition_immutable(previous: str | None, new: str | None) -> None:
    """Permite el no-op y rechaza cualquier cambio de la condición física.

    La función es pura: no normaliza ni muta los valores recibidos, porque la
    comparación debe ser exactamente la evidencia guardada contra la nueva.
    """
    if new == previous:
        return
    raise ImmutableFieldError(
        field="physical_condition",
        previous=previous,
        new=new,
    )
