"""Modelos de equipos y del contador de códigos (RF-03 / RN-02).

`equipments` **no** tiene dueño: la propiedad se registra por servicio en
`service_orders` (spec §5, plan §2.2). El código interno sale de
`code_counters`, nunca de `MAX(id) + 1` (decisión D-05).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Equipment(Base):
    """Equipo identificado por un código interno correlativo único."""

    __tablename__ = "equipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_code: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    device_type_id: Mapped[int] = mapped_column(
        ForeignKey("device_types.id", ondelete="RESTRICT"), nullable=False
    )
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="RESTRICT"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("length(trim(internal_code)) > 0", name="internal_code_not_blank"),
        CheckConstraint("length(trim(model)) > 0", name="model_not_blank"),
        Index("ix_equipments_serial_number", "serial_number"),
    )


class CodeCounter(Base):
    """Secuencia correlativa por nombre (`'equipment'`)."""

    __tablename__ = "code_counters"

    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (CheckConstraint("last_value >= 0", name="last_value_non_negative"),)
