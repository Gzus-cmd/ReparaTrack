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


class ValidationError(DomainError):
    """Un dato de entrada no cumple las reglas de negocio del caso de uso."""

    code = "validation_error"
    default_message = "Datos de entrada inválidos."

    def __init__(self, field: str, message: str | None = None, **details: Any) -> None:
        super().__init__(message, field=field, **details)


class NotFoundError(DomainError):
    """El recurso solicitado no existe."""

    code = "not_found"
    default_message = "Recurso no encontrado."

    def __init__(self, resource: str, identifier: Any, message: str | None = None) -> None:
        super().__init__(
            message or f"No se encontró {resource} con identificador {identifier}.",
            resource=resource,
            id=identifier,
        )


class CatalogDuplicateError(DomainError):
    """RF-01: el nombre normalizado ya existe en el maestro (incluye inactivos)."""

    code = "catalog_duplicate"
    default_message = "El valor del maestro ya existe."

    def __init__(self, name: str, existing_id: int | None = None, message: str | None = None):
        super().__init__(
            message or f"Ya existe un valor con el nombre {name!r} en este maestro.",
            name=name,
            existing_id=existing_id,
        )


class CatalogValueInUseError(DomainError):
    """RN-09: un valor referenciado no se borra; se desactiva."""

    code = "catalog_value_in_use"
    default_message = "El valor del maestro está en uso y no se puede eliminar."

    def __init__(
        self,
        catalog_id: int,
        usage_count: int,
        hint: str = "Use la baja lógica para desactivar el valor sin eliminarlo.",
        message: str | None = None,
    ) -> None:
        super().__init__(
            message or "El valor del maestro está en uso: se desactiva en vez de borrarse.",
            catalog_id=catalog_id,
            usage_count=usage_count,
            hint=hint,
        )


class DocumentDuplicateError(DomainError):
    """RF-02: el documento es un dato diferenciador y no se repite."""

    code = "document_duplicate"
    default_message = "El documento ya está registrado para otro cliente."

    def __init__(self, document: str, message: str | None = None) -> None:
        super().__init__(
            message or f"El documento {document!r} ya está registrado para otro cliente.",
            document=document,
        )


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
