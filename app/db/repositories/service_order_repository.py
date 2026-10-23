"""Repositorio de órdenes de servicio y sus líneas de detalle (RF-04, RF-05)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.db.models.service_order import ServiceDetail, ServiceOrder
from app.domain.enums import ServiceStatus
from app.services.ports import ServiceDetailRecord, ServiceOrderRecord


def _to_order_record(order: ServiceOrder) -> ServiceOrderRecord:
    return ServiceOrderRecord(
        id=order.id,
        equipment_id=order.equipment_id,
        customer_id=order.customer_id,
        received_at=order.received_at,
        reported_failure=order.reported_failure,
        physical_condition=order.physical_condition,
        accessories=order.accessories,
        password_requested=order.password_requested,
        status=ServiceStatus(order.status).value,
        delivered_at=order.delivered_at,
        origin_service_id=order.origin_service_id,
        created_at=order.created_at,
    )


def _to_detail_record(detail: ServiceDetail) -> ServiceDetailRecord:
    return ServiceDetailRecord(
        id=detail.id,
        service_order_id=detail.service_order_id,
        operation_type_id=detail.operation_type_id,
        component_id=detail.component_id,
        description=detail.description,
        created_at=detail.created_at,
    )


def _order_filters(
    *,
    status: str | None,
    customer_id: int | None,
    equipment_id: int | None,
) -> list[ColumnElement[bool]]:
    """Condiciones de la bandeja, compartidas por el listado y el conteo."""
    conditions: list[ColumnElement[bool]] = []
    if status is not None:
        conditions.append(ServiceOrder.status == ServiceStatus.parse(status))
    if customer_id is not None:
        conditions.append(ServiceOrder.customer_id == customer_id)
    if equipment_id is not None:
        conditions.append(ServiceOrder.equipment_id == equipment_id)
    return conditions


class SqlServiceOrderRepository:
    """Implementación concreta de `ServiceOrderRepository` sobre SQLite."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        equipment_id: int,
        customer_id: int,
        received_at: datetime,
        reported_failure: str,
        physical_condition: str,
        accessories: str,
        password_requested: bool = False,
        status: str = ServiceStatus.RECEIVED.value,
        delivered_at: datetime | None = None,
        origin_service_id: int | None = None,
    ) -> ServiceOrderRecord:
        order = ServiceOrder(
            equipment_id=equipment_id,
            customer_id=customer_id,
            received_at=received_at,
            reported_failure=reported_failure,
            physical_condition=physical_condition,
            accessories=accessories,
            password_requested=password_requested,
            status=ServiceStatus.parse(status),
            delivered_at=delivered_at,
            origin_service_id=origin_service_id,
        )
        self._session.add(order)
        self._session.flush()
        self._session.refresh(order)
        return _to_order_record(order)

    def get(self, service_order_id: int) -> ServiceOrderRecord | None:
        order = self._session.get(ServiceOrder, service_order_id)
        return None if order is None else _to_order_record(order)

    def list(
        self,
        *,
        status: str | None = None,
        customer_id: int | None = None,
        equipment_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ServiceOrderRecord]:
        statement = (
            select(ServiceOrder)
            .where(
                *_order_filters(
                    status=status, customer_id=customer_id, equipment_id=equipment_id
                )
            )
            .order_by(ServiceOrder.received_at.desc(), ServiceOrder.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_order_record(order) for order in self._session.scalars(statement)]

    def count(
        self,
        *,
        status: str | None = None,
        customer_id: int | None = None,
        equipment_id: int | None = None,
    ) -> int:
        statement = select(func.count()).select_from(ServiceOrder).where(
            *_order_filters(
                status=status, customer_id=customer_id, equipment_id=equipment_id
            )
        )
        return self._session.scalar(statement) or 0

    def update_status(
        self,
        service_order_id: int,
        *,
        status: str,
        delivered_at: datetime | None = None,
    ) -> ServiceOrderRecord | None:
        """Actualiza estado y fecha de entrega dentro de la transacción abierta."""
        order = self._session.get(ServiceOrder, service_order_id)
        if order is None:
            return None
        order.status = ServiceStatus.parse(status)
        order.delivered_at = delivered_at
        self._session.flush()
        self._session.refresh(order)
        return _to_order_record(order)

    def add_detail(
        self,
        *,
        service_order_id: int,
        operation_type_id: int,
        description: str,
        component_id: int | None = None,
    ) -> ServiceDetailRecord:
        detail = ServiceDetail(
            service_order_id=service_order_id,
            operation_type_id=operation_type_id,
            description=description,
            component_id=component_id,
        )
        self._session.add(detail)
        self._session.flush()
        self._session.refresh(detail)
        return _to_detail_record(detail)

    def list_details(self, service_order_id: int) -> Sequence[ServiceDetailRecord]:
        details = self._session.scalars(
            select(ServiceDetail)
            .where(ServiceDetail.service_order_id == service_order_id)
            .order_by(ServiceDetail.id)
        )
        return [_to_detail_record(detail) for detail in details]

    def get_detail(
        self, service_order_id: int, detail_id: int
    ) -> ServiceDetailRecord | None:
        detail = self._session.scalars(
            select(ServiceDetail).where(
                ServiceDetail.id == detail_id,
                ServiceDetail.service_order_id == service_order_id,
            )
        ).first()
        return None if detail is None else _to_detail_record(detail)

    def delete_detail(self, service_order_id: int, detail_id: int) -> bool:
        """Borra solo si la línea pertenece a la orden indicada."""
        detail = self._session.get(ServiceDetail, detail_id)
        if detail is None or detail.service_order_id != service_order_id:
            return False
        self._session.delete(detail)
        self._session.flush()
        return True

    def count_details(self, service_order_id: int) -> int:
        return (
            self._session.scalar(
                select(func.count())
                .select_from(ServiceDetail)
                .where(ServiceDetail.service_order_id == service_order_id)
            )
            or 0
        )

    def count_for_equipment(self, equipment_id: int) -> int:
        """Cantidad de servicios registrados para un equipo (RF-03)."""
        return (
            self._session.scalar(
                select(func.count())
                .select_from(ServiceOrder)
                .where(ServiceOrder.equipment_id == equipment_id)
            )
            or 0
        )

    def find_current_customer_id(self, equipment_id: int) -> int | None:
        """Cliente del último servicio del equipo (el dueño vigente)."""
        return self._session.scalar(
            select(ServiceOrder.customer_id)
            .where(ServiceOrder.equipment_id == equipment_id)
            .order_by(ServiceOrder.received_at.desc(), ServiceOrder.id.desc())
            .limit(1)
        )
