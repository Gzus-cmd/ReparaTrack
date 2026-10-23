"""Repositorio de equipos con código correlativo atómico (RF-03 / RN-02).

El código sale de `code_counters` dentro de la misma transacción del alta
(decisión D-05): un rollback revierte el incremento y no consume correlativo,
y nunca se usa `MAX(id) + 1`.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.equipment import CodeCounter, Equipment
from app.domain.codes import format_internal_code, parse_internal_code
from app.domain.errors import DomainError
from app.services.ports import EquipmentRecord

EQUIPMENT_COUNTER = "equipment"


class DuplicateInternalCodeError(DomainError):
    """El código interno ya existe: conflicto de negocio, no error técnico."""

    code = "duplicate_internal_code"
    default_message = "El código interno del equipo ya está en uso."


def _to_record(equipment: Equipment) -> EquipmentRecord:
    return EquipmentRecord(
        id=equipment.id,
        internal_code=equipment.internal_code,
        device_type_id=equipment.device_type_id,
        brand_id=equipment.brand_id,
        model=equipment.model,
        serial_number=equipment.serial_number,
        created_at=equipment.created_at,
    )


class SqlEquipmentRepository:
    """Implementación concreta de `EquipmentRepository`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        device_type_id: int,
        brand_id: int,
        model: str,
        serial_number: str | None = None,
    ) -> EquipmentRecord:
        self._ensure_counter()
        internal_code = self._next_internal_code()
        equipment = Equipment(
            internal_code=internal_code,
            device_type_id=device_type_id,
            brand_id=brand_id,
            model=" ".join(model.split()),
            serial_number=serial_number.strip() if serial_number else None,
        )
        self._session.add(equipment)
        try:
            self._session.flush()
        except IntegrityError as exc:
            if "internal_code" in str(exc.orig):
                raise DuplicateInternalCodeError(internal_code=internal_code) from exc
            raise
        self._session.refresh(equipment)
        return _to_record(equipment)

    def get(self, equipment_id: int) -> EquipmentRecord | None:
        equipment = self._session.get(Equipment, equipment_id)
        return None if equipment is None else _to_record(equipment)

    def find_by_internal_code(self, internal_code: str) -> EquipmentRecord | None:
        try:
            sequence = parse_internal_code(internal_code)
        except (TypeError, ValueError):
            return None
        normalized = format_internal_code(sequence)
        equipment = self._session.scalars(
            select(Equipment).where(Equipment.internal_code == normalized)
        ).first()
        return None if equipment is None else _to_record(equipment)

    def find_by_serial_number(self, serial_number: str) -> EquipmentRecord | None:
        """Devuelve el primer equipo registrado con ese serial (identidad débil).

        El serial puede repetirse (plan §2.5): el código interno sigue siendo la
        identidad fuerte (D-06) y esta búsqueda es solo una ayuda de recepción.
        """
        if not serial_number or not serial_number.strip():
            return None
        equipment = self._session.scalars(
            select(Equipment)
            .where(Equipment.serial_number == serial_number.strip())
            .order_by(Equipment.id)
        ).first()
        return None if equipment is None else _to_record(equipment)

    def _ensure_counter(self) -> None:
        if self._session.get(CodeCounter, EQUIPMENT_COUNTER) is None:
            self._session.add(CodeCounter(name=EQUIPMENT_COUNTER, last_value=0))
            self._session.flush()

    def _next_internal_code(self) -> str:
        """Incrementa el contador con un `UPDATE` atómico en la transacción."""
        result = self._session.execute(
            update(CodeCounter)
            .where(CodeCounter.name == EQUIPMENT_COUNTER)
            .values(last_value=CodeCounter.last_value + 1)
        )
        if result.rowcount != 1:  # pragma: no cover - defensa ante contador ausente
            raise RuntimeError("El contador de códigos de equipo no está inicializado.")
        last_value = self._session.scalar(
            select(CodeCounter.last_value).where(CodeCounter.name == EQUIPMENT_COUNTER)
        )
        return format_internal_code(int(last_value))
