"""Máquina de estados cerrada de los servicios (RN-05).

La matriz es un dato: no hay ramas especiales por estado. Las 15 aristas
válidas incluyen `READY_FOR_PICKUP → IN_REPAIR` (retrabajo) y dejan a
`DELIVERED` y `ABANDONED` sin salidas.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from app.domain.enums import ServiceStatus
from app.domain.errors import InvalidTransitionError

TRANSITIONS: Mapping[ServiceStatus, frozenset[ServiceStatus]] = MappingProxyType(
    {
        ServiceStatus.RECEIVED: frozenset({ServiceStatus.DIAGNOSING}),
        ServiceStatus.DIAGNOSING: frozenset(
            {
                ServiceStatus.AWAITING_APPROVAL,
                ServiceStatus.AWAITING_PART,
                ServiceStatus.NOT_REPARABLE,
            }
        ),
        ServiceStatus.AWAITING_APPROVAL: frozenset(
            {
                ServiceStatus.IN_REPAIR,
                ServiceStatus.REJECTED,
                ServiceStatus.ABANDONED,
            }
        ),
        ServiceStatus.AWAITING_PART: frozenset({ServiceStatus.IN_REPAIR}),
        ServiceStatus.IN_REPAIR: frozenset(
            {ServiceStatus.READY_FOR_PICKUP, ServiceStatus.AWAITING_PART}
        ),
        ServiceStatus.NOT_REPARABLE: frozenset({ServiceStatus.DELIVERED}),
        ServiceStatus.REJECTED: frozenset({ServiceStatus.DELIVERED}),
        ServiceStatus.READY_FOR_PICKUP: frozenset(
            {
                ServiceStatus.DELIVERED,
                ServiceStatus.ABANDONED,
                ServiceStatus.IN_REPAIR,
            }
        ),
        ServiceStatus.DELIVERED: frozenset(),
        ServiceStatus.ABANDONED: frozenset(),
    }
)


def _as_status(status: ServiceStatus | str) -> ServiceStatus:
    """Normaliza la clave recibida; lanza `UnknownStatusError` si no existe."""
    return status if isinstance(status, ServiceStatus) else ServiceStatus.parse(status)


def allowed_targets(status: ServiceStatus | str) -> frozenset[ServiceStatus]:
    """Destinos alcanzables desde `status` según la matriz."""
    return TRANSITIONS[_as_status(status)]


def can_transition(current: ServiceStatus | str, target: ServiceStatus | str) -> bool:
    """Indica si el par origen/destino pertenece a la matriz."""
    return _as_status(target) in allowed_targets(current)


def assert_transition(
    current: ServiceStatus | str,
    target: ServiceStatus | str,
    allowed: Iterable[ServiceStatus] | None = None,
) -> None:
    """Valida la arista y lanza `InvalidTransitionError` con el contexto."""
    origin = _as_status(current)
    destination = _as_status(target)
    permitted = TRANSITIONS[origin]
    if destination not in permitted:
        raise InvalidTransitionError(origin, destination, allowed or permitted)
