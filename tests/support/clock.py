"""Reloj congelado que implementa el puerto `Clock` sin dormir en los tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

DEFAULT_NOW = datetime(2026, 10, 22, 15, 0, tzinfo=UTC)


class FrozenClock:
    """Reloj determinista: `now()` devuelve siempre el instante fijado."""

    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or DEFAULT_NOW

    def now(self) -> datetime:
        return self._now

    def travel(self, *, days: int = 0, hours: int = 0, minutes: int = 0) -> datetime:
        """Avanza el reloj sin `sleep` y devuelve el nuevo instante."""
        self._now = self._now + timedelta(days=days, hours=hours, minutes=minutes)
        return self._now

    def set(self, moment: datetime) -> datetime:
        """Fija un instante explícito."""
        self._now = moment
        return self._now
