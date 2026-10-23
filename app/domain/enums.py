"""Estados del servicio: claves en inglés y etiquetas visibles en español."""

from __future__ import annotations

from enum import StrEnum

from app.domain.errors import UnknownStatusError


class ServiceStatus(StrEnum):
    """Los 10 estados de un servicio (RN-05 / spec §6)."""

    RECEIVED = "RECEIVED"
    DIAGNOSING = "DIAGNOSING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    AWAITING_PART = "AWAITING_PART"
    IN_REPAIR = "IN_REPAIR"
    NOT_REPARABLE = "NOT_REPARABLE"
    REJECTED = "REJECTED"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    DELIVERED = "DELIVERED"
    ABANDONED = "ABANDONED"

    @property
    def label(self) -> str:
        """Etiqueta en español neutro para la UI."""
        return STATUS_LABELS[self]

    @property
    def is_terminal(self) -> bool:
        """Indica si el estado cierra el ciclo de vida del servicio."""
        return self in TERMINAL_STATUSES

    @classmethod
    def parse(cls, value: ServiceStatus | str) -> ServiceStatus:
        """Normaliza una clave de estado; rechaza etiquetas y valores ajenos."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().upper()
            try:
                return cls(normalized)
            except ValueError:
                pass
        raise UnknownStatusError(value)


STATUS_LABELS: dict[ServiceStatus, str] = {
    ServiceStatus.RECEIVED: "Recibido",
    ServiceStatus.DIAGNOSING: "En diagnóstico",
    ServiceStatus.AWAITING_APPROVAL: "Esperando aprobación",
    ServiceStatus.AWAITING_PART: "Esperando repuesto",
    ServiceStatus.IN_REPAIR: "En reparación",
    ServiceStatus.NOT_REPARABLE: "No reparable",
    ServiceStatus.REJECTED: "Rechazado",
    ServiceStatus.READY_FOR_PICKUP: "Listo para entrega",
    ServiceStatus.DELIVERED: "Entregado",
    ServiceStatus.ABANDONED: "Abandonado",
}

TERMINAL_STATUSES: frozenset[ServiceStatus] = frozenset(
    {ServiceStatus.DELIVERED, ServiceStatus.ABANDONED}
)
