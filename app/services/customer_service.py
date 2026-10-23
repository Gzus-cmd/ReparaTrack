"""Servicio de clientes: alta, búsqueda y actualización de contacto (RF-02 / T-18).

Valida el contacto mínimo (nombre y teléfono), el formato opcional del correo y
la unicidad del documento. No importa SQLAlchemy ni FastAPI.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.domain.errors import DocumentDuplicateError, NotFoundError, ValidationError
from app.services.ports import CustomerRecord, CustomerRepository

CUSTOMER_RESOURCE = "el cliente"

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class CustomerPage:
    """Página de clientes con el total que necesita la UI."""

    items: tuple[CustomerRecord, ...]
    total: int


class CustomerService:
    """Casos de uso del cliente sobre el puerto `CustomerRepository`."""

    def __init__(self, repository: CustomerRepository) -> None:
        self._repository = repository

    def create(
        self,
        *,
        name: str,
        phone: str,
        email: str | None = None,
        document: str | None = None,
    ) -> CustomerRecord:
        """Registra un cliente con su contacto y documento diferenciador."""
        display_name = self._required_text(name, "name", "El nombre del cliente")
        display_phone = self._required_text(phone, "phone", "El teléfono del cliente")
        display_email = self._optional_email(email)
        display_document = self._optional_document(document)
        if display_document is not None:
            self._ensure_document_is_free(display_document)
        return self._repository.add(
            name=display_name,
            phone=display_phone,
            email=display_email,
            document=display_document,
        )

    def get(self, customer_id: int) -> CustomerRecord:
        """Devuelve el cliente o falla con `not_found`."""
        customer = self._repository.get(customer_id)
        if customer is None:
            raise NotFoundError(CUSTOMER_RESOURCE, customer_id)
        return customer

    def search(self, query: str = "", *, limit: int = 50, offset: int = 0) -> CustomerPage:
        """Busca por nombre, teléfono o documento, sin distinguir mayúsculas."""
        items = self._repository.search(query, limit=limit, offset=offset)
        return CustomerPage(items=tuple(items), total=self._repository.count(query))

    def update(self, customer_id: int, changes: Mapping[str, Any]) -> CustomerRecord:
        """Actualiza los campos de contacto recibidos y valida los demás."""
        current = self.get(customer_id)
        normalized: dict[str, str | None] = {}
        if "name" in changes:
            normalized["name"] = self._required_text(
                str(changes["name"] or ""), "name", "El nombre del cliente"
            )
        if "phone" in changes:
            normalized["phone"] = self._required_text(
                str(changes["phone"] or ""), "phone", "El teléfono del cliente"
            )
        if "email" in changes:
            normalized["email"] = self._optional_email(changes["email"])
        if "document" in changes:
            document = self._optional_document(changes["document"])
            if document is not None:
                self._ensure_document_is_free(document, customer_id=customer_id)
            normalized["document"] = document
        if not normalized:
            return current
        updated = self._repository.update_contact(customer_id, normalized)
        if updated is None:  # pragma: no cover - defensa ante borrado concurrente
            raise NotFoundError(CUSTOMER_RESOURCE, customer_id)
        return updated

    def _ensure_document_is_free(self, document: str, *, customer_id: int | None = None) -> None:
        existing = self._repository.find_by_document(document)
        if existing is not None and existing.id != customer_id:
            raise DocumentDuplicateError(document)

    @staticmethod
    def _required_text(value: str, field: str, label: str) -> str:
        display = " ".join(value.split())
        if not display:
            raise ValidationError(field, f"{label} no puede estar vacío.")
        return display

    @staticmethod
    def _optional_email(value: Any) -> str | None:
        display = " ".join(str(value).split()) if value is not None else ""
        if not display:
            return None
        if not _EMAIL_PATTERN.match(display):
            raise ValidationError("email", "El correo no tiene un formato válido.")
        return display

    @staticmethod
    def _optional_document(value: Any) -> str | None:
        display = str(value).strip() if value is not None else ""
        return display or None
