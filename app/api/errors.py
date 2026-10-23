"""Traducción de errores de dominio y de validación al contrato HTTP.

El código HTTP se decide por `error.code` (plan §3), nunca por el tipo concreto:
así `DuplicateInternalCodeError` (definido en la capa de persistencia) también
responde `409` sin que la API dependa de `app.db`.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.errors import DomainError, ValidationError

STATUS_BY_CODE: dict[str, int] = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "validation_error": 422,
    "unknown_status": 422,
    "equipment_source_invalid": 422,
    "immutable_field": 422,
    "catalog_duplicate": status.HTTP_409_CONFLICT,
    "catalog_value_in_use": status.HTTP_409_CONFLICT,
    "document_duplicate": status.HTTP_409_CONFLICT,
    "duplicate_internal_code": status.HTTP_409_CONFLICT,
    "invalid_transition": status.HTTP_409_CONFLICT,
    "details_required": status.HTTP_409_CONFLICT,
    "threshold_not_reached": status.HTTP_409_CONFLICT,
    "confirmation_required": status.HTTP_409_CONFLICT,
    "service_order_terminal": status.HTTP_409_CONFLICT,
    "warranty_expired": status.HTTP_409_CONFLICT,
    "warranty_equipment_mismatch": status.HTTP_409_CONFLICT,
    "origin_not_delivered": status.HTTP_409_CONFLICT,
    "origin_already_linked": status.HTTP_409_CONFLICT,
}

DEFAULT_ERROR_STATUS = status.HTTP_409_CONFLICT

_LOCATION_PREFIXES = frozenset({"body", "query", "path", "header", "cookie"})


def _field_from_location(location: Any) -> str | None:
    """Extrae el nombre del campo desde la ubicación de Pydantic."""
    parts = [part for part in location if part not in _LOCATION_PREFIXES]
    return None if not parts else str(parts[-1])


def _build_validation_envelope(errors: list[dict[str, Any]]) -> dict[str, Any]:
    first = errors[0] if errors else {}
    field = _field_from_location(first.get("loc", ()))
    normalized = [
        {
            "field": _field_from_location(error.get("loc", ())),
            "message": str(error.get("msg", "")),
            "type": str(error.get("type", "")),
        }
        for error in errors
    ]
    return ValidationError(
        field or "body",
        "Datos de entrada inválidos.",
        errors=normalized,
    ).to_envelope()


def register_error_handlers(app: FastAPI) -> None:
    """Registra los manejadores uniformes de error de la aplicación."""

    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=STATUS_BY_CODE.get(exc.code, DEFAULT_ERROR_STATUS),
            content=exc.to_envelope(),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_build_validation_envelope(list(exc.errors())),
        )
