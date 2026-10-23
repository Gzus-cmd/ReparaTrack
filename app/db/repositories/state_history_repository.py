"""Repositorio de la bitácora de estados: solo alta y lectura (RN-05)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.state_history import StateHistory
from app.domain.enums import ServiceStatus
from app.services.ports import StateHistoryRecord


def _to_record(entry: StateHistory) -> StateHistoryRecord:
    return StateHistoryRecord(
        id=entry.id,
        service_order_id=entry.service_order_id,
        status=ServiceStatus(entry.status).value,
        changed_at=entry.changed_at,
        comment=entry.comment,
    )


class SqlStateHistoryRepository:
    """Append-only: la clase no publica `update` ni `delete`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        service_order_id: int,
        status: str,
        changed_at: datetime,
        comment: str | None = None,
    ) -> StateHistoryRecord:
        entry = StateHistory(
            service_order_id=service_order_id,
            status=ServiceStatus.parse(status),
            changed_at=changed_at,
            comment=comment,
        )
        self._session.add(entry)
        self._session.flush()
        self._session.refresh(entry)
        return _to_record(entry)

    def list_for_order(self, service_order_id: int) -> Sequence[StateHistoryRecord]:
        entries = self._session.scalars(
            select(StateHistory)
            .where(StateHistory.service_order_id == service_order_id)
            .order_by(StateHistory.changed_at, StateHistory.id)
        )
        return [_to_record(entry) for entry in entries]
