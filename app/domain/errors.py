"""Errores de dominio con código estable y detalles serializables."""

from __future__ import annotations

from typing import Any


def _json_safe(value: Any) -> Any:
    """Convierte un valor de contexto en algo serializable a JSON."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return str(value)


def _status_value(status: Any) -> Any:
    """Extrae el valor textual de un estado, sin acoplarse al enum."""
    enum_value = getattr(status, "value", None)
    return enum_value if isinstance(enum_value, str) else status


class DomainError(Exception):
    """Base de todos los errores de negocio.

    Cada subclase declara un `code` estable en inglés y arma `details`
    con el contexto que la API necesita para responder.
    """

    code: str = "domain_error"
    default_message: str = "Error de dominio."

    def __init__(self, message: str | None = None, **details: Any) -> None:
        self.message = message or self.default_message
        self.details = {key: _json_safe(value) for key, value in details.items()}
        super().__init__(self.message)

    def to_envelope(self) -> dict[str, Any]:
        """Devuelve la forma `error.code/message/details` del contrato."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": dict(self.details),
            }
        }


class InvalidTransitionError(DomainError):
    """La matriz cerrada de RN-05 no admite el par origen/destino."""

    code = "invalid_transition"
    default_message = "Transición de estado no permitida."

    def __init__(
        self,
        from_status: Any,
        to_status: Any,
        allowed: Any = (),
        message: str | None = None,
    ) -> None:
        origin = _status_value(from_status)
        target = _status_value(to_status)
        allowed_values = sorted(_status_value(status) for status in allowed)
        super().__init__(
            message or f"Transición inválida de {origin} a {target}.",
            from_status=origin,
            to_status=target,
            allowed=allowed_values,
        )


class DetailsRequiredError(DomainError):
    """RN-03: `READY_FOR_PICKUP` exige al menos una línea de detalle."""

    code = "details_required"
    default_message = "Se requiere al menos una línea de detalle para listo para entrega."

    def __init__(self, details_count: int = 0, message: str | None = None) -> None:
        super().__init__(message, details_count=details_count)


class ThresholdNotReachedError(DomainError):
    """El estado no permaneció los días mínimos que exige la regla."""

    code = "threshold_not_reached"
    default_message = "No se alcanzó el umbral de días requerido para el abandono."

    def __init__(
        self,
        rule: str,
        days_in_status: int,
        required_days: int,
        message: str | None = None,
    ) -> None:
        super().__init__(
            message
            or (
                f"La regla {rule} exige al menos {required_days} días en el estado "
                f"y solo han transcurrido {days_in_status}."
            ),
            rule=rule,
            days_in_status=days_in_status,
            required_days=required_days,
        )


class ConfirmationRequiredError(DomainError):
    """El abandono siempre exige confirmación explícita del técnico."""

    code = "confirmation_required"
    default_message = "La transición requiere confirmación explícita."

    def __init__(self, to_status: Any, message: str | None = None) -> None:
        target = _status_value(to_status)
        super().__init__(
            message or f"La transición a {target} requiere confirmación explícita.",
            to_status=target,
        )


class UnknownStatusError(DomainError):
    """La clave recibida no pertenece a los 10 estados del servicio."""

    code = "unknown_status"
    default_message = "Estado desconocido."

    def __init__(self, value: Any, message: str | None = None) -> None:
        super().__init__(
            message or f"Estado desconocido: {value!r}.",
            value=value,
        )
