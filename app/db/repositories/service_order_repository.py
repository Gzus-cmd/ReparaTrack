"""Repositorio de órdenes de servicio y sus líneas de detalle (RF-04, RF-05)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
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
