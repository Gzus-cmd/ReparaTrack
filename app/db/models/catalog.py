"""Modelos de los cuatro maestros (RF-01 / RN-09)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CatalogMixin:
    """Columnas comunes a los maestros: PK, baja lógica y alta."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DeviceType(CatalogMixin, Base):
    """Tipo de dispositivo: laptop, PC o impresora."""

    __tablename__ = "device_types"

    name: Mapped[str] = mapped_column(String(60), nullable=False)

    __table_args__ = (
        UniqueConstraint("name", name="uq_device_types_name"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )


class Brand(CatalogMixin, Base):
    """Marca del equipo."""

    __tablename__ = "brands"

    name: Mapped[str] = mapped_column(String(60), nullable=False)

    __table_args__ = (
        UniqueConstraint("name", name="uq_brands_name"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )


class Component(CatalogMixin, Base):
    """Componente reemplazado o revisado (RAM, disco, pasta térmica…)."""

    __tablename__ = "components"

    name: Mapped[str] = mapped_column(String(80), nullable=False)

    __table_args__ = (
        UniqueConstraint("name", name="uq_components_name"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )


class OperationType(CatalogMixin, Base):
    """Tipo de operación; "Diagnóstico" es un dato sembrado (D-09)."""

    __tablename__ = "operation_types"

    name: Mapped[str] = mapped_column(String(60), nullable=False)

    __table_args__ = (
        UniqueConstraint("name", name="uq_operation_types_name"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )
