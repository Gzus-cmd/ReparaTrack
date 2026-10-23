"""Repositorio de clientes con búsqueda por nombre, teléfono o documento (RF-02)."""

from __future__ import annotations

from sqlalchemy import or_, select
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

    def search(self, query: str, *, limit: int = 50, offset: int = 0) -> list[CustomerRecord]:
        pattern = f"%{query.strip()}%"
        customers = self._session.scalars(
            select(Customer)
            .where(
                or_(
                    Customer.name.ilike(pattern),
                    Customer.phone.ilike(pattern),
                    Customer.document.ilike(pattern),
                )
            )
            .order_by(Customer.name, Customer.id)
            .limit(limit)
            .offset(offset)
        )
        return [_to_record(customer) for customer in customers]
