"""Repositorio de clientes con búsqueda por nombre, teléfono o documento (RF-02)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.db.models.customer import Customer
from app.services.ports import CustomerRecord


def _to_record(customer: Customer) -> CustomerRecord:
    return CustomerRecord(
        id=customer.id,
        name=customer.name,
        phone=customer.phone,
        email=customer.email,
        document=customer.document,
        created_at=customer.created_at,
    )


def _search_filter(query: str) -> ColumnElement[bool]:
    """Filtro único de búsqueda, reutilizado por el listado y el conteo."""
    pattern = f"%{query.strip()}%"
    return or_(
        Customer.name.ilike(pattern),
        Customer.phone.ilike(pattern),
        Customer.document.ilike(pattern),
    )


class SqlCustomerRepository:
    """Implementación concreta de `CustomerRepository`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        name: str,
        phone: str,
        email: str | None = None,
        document: str | None = None,
    ) -> CustomerRecord:
        customer = Customer(
            name=" ".join(name.split()),
            phone=phone.strip(),
            email=email.strip() if email else None,
            document=document.strip() if document else None,
        )
        self._session.add(customer)
        self._session.flush()
        self._session.refresh(customer)
        return _to_record(customer)

    def get(self, customer_id: int) -> CustomerRecord | None:
        customer = self._session.get(Customer, customer_id)
        return None if customer is None else _to_record(customer)

    def find_by_document(self, document: str) -> CustomerRecord | None:
        normalized = document.strip()
        if not normalized:
            return None
        customer = self._session.scalars(
            select(Customer).where(Customer.document == normalized)
        ).first()
        return None if customer is None else _to_record(customer)

    def count(self, query: str = "") -> int:
        statement = select(func.count()).select_from(Customer)
        if query.strip():
            statement = statement.where(_search_filter(query))
        return self._session.scalar(statement) or 0

    def update_contact(self, customer_id: int, changes: Mapping[str, Any]) -> CustomerRecord | None:
        customer = self._session.get(Customer, customer_id)
        if customer is None:
            return None
        for field in ("name", "phone", "email", "document"):
            if field in changes:
                setattr(customer, field, changes[field])
        self._session.flush()
        self._session.refresh(customer)
        return _to_record(customer)

    def search(self, query: str, *, limit: int = 50, offset: int = 0) -> list[CustomerRecord]:
        statement = select(Customer)
        if query.strip():
            statement = statement.where(_search_filter(query))
        customers = self._session.scalars(
            statement.order_by(Customer.name, Customer.id).limit(limit).offset(offset)
        )
        return [_to_record(customer) for customer in customers]
