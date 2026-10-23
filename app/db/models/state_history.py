"""Bitácora inmutable de estados del servicio (RF-06 / RN-05)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.service_order import service_status_column_type
from app.domain.enums import ServiceStatus


class StateHistory(Base):
    """Fila append-only: solo se inserta y se lee, nunca se actualiza."""

    __tablename__ = "state_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_order_id: Mapped[int] = mapped_column(
        ForeignKey("service_orders.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ServiceStatus] = mapped_column(service_status_column_type(), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        Index(
            "ix_state_history_service_status",
            "service_order_id",
            "status",
            "changed_at",
        ),
        Index("ix_state_history_changed_at", "changed_at"),
    )
