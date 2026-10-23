"""Modelos de la orden de servicio y sus líneas de detalle (RF-04, RF-05)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import ServiceStatus

DELIVERED_STATUS = ServiceStatus.DELIVERED.value


def service_status_column_type() -> Enum:
    """Enum de estado como VARCHAR + CHECK real en SQLite (riesgo R-03)."""
    return Enum(
        ServiceStatus,
        name="service_status",
        native_enum=False,
        create_constraint=True,
        values_callable=lambda enum_type: [member.value for member in enum_type],
        length=24,
    )


class ServiceOrder(Base):
    """Servicio prestado a un equipo para un cliente (la propiedad vive aquí)."""

    __tablename__ = "service_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("equipments.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reported_failure: Mapped[str] = mapped_column(String(500), nullable=False)
    physical_condition: Mapped[str] = mapped_column(String(500), nullable=False)
    accessories: Mapped[str] = mapped_column(String(500), nullable=False)
    password_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    status: Mapped[ServiceStatus] = mapped_column(
        service_status_column_type(),
        nullable=False,
        default=ServiceStatus.RECEIVED,
        server_default=ServiceStatus.RECEIVED.value,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    origin_service_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_orders.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("origin_service_id", name="uq_service_orders_origin_service_id"),
        CheckConstraint(
            "origin_service_id IS NULL OR origin_service_id <> id",
            name="origin_not_self",
        ),
        CheckConstraint(
            f"(status = '{DELIVERED_STATUS}') = (delivered_at IS NOT NULL)",
            name="delivery_consistency",
        ),
        CheckConstraint("length(trim(reported_failure)) > 0", name="reported_failure_not_blank"),
        CheckConstraint(
            "length(trim(physical_condition)) > 0", name="physical_condition_not_blank"
        ),
        CheckConstraint("length(trim(accessories)) > 0", name="accessories_not_blank"),
        Index("ix_service_orders_status", "status"),
        Index("ix_service_orders_equipment_id", "equipment_id"),
        Index("ix_service_orders_customer_id", "customer_id"),
        Index("ix_service_orders_received_at", "received_at"),
        Index("ix_service_orders_status_received", "status", "received_at"),
    )


class ServiceDetail(Base):
    """Línea de trabajo: operación, componente opcional y descripción."""

    __tablename__ = "service_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_order_id: Mapped[int] = mapped_column(
        ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False
    )
    operation_type_id: Mapped[int] = mapped_column(
        ForeignKey("operation_types.id", ondelete="RESTRICT"), nullable=False
    )
    component_id: Mapped[int | None] = mapped_column(
        ForeignKey("components.id", ondelete="RESTRICT"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("length(trim(description)) > 0", name="description_not_blank"),
        Index("ix_service_details_service_order_id", "service_order_id"),
    )
