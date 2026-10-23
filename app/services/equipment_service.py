"""Servicio de equipos: alta con código correlativo y búsqueda (RF-03 / T-19, T-20).

El correlativo lo entrega `EquipmentRepository` (T-15): el servicio no lo
reimplementa ni usa `MAX(id) + 1`. No importa SQLAlchemy ni FastAPI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.errors import NotFoundError, ValidationError
from app.services.ports import (
    CatalogRepository,
    CatalogValue,
    CustomerRecord,
    CustomerRepository,
    EquipmentRecord,
    EquipmentRepository,
    ServiceOrderRepository,
)

EQUIPMENT_RESOURCE = "el equipo"


@dataclass(frozen=True, slots=True)
class CatalogReference:
    """Referencia mínima a un valor de maestro para la respuesta de la API."""

    id: int
    name: str


@dataclass(frozen=True, slots=True)
class CustomerReference:
    """Contacto mínimo del dueño vigente del equipo."""

    id: int
    name: str
    phone: str


@dataclass(frozen=True, slots=True)
class EquipmentView:
    """Equipo con sus referencias y el historial anticipado (RF-03)."""

    id: int
    internal_code: str
    device_type: CatalogReference
    brand: CatalogReference
    model: str
    serial_number: str | None
    created_at: datetime
    current_owner: CustomerReference | None
    previous_services_count: int


class EquipmentService:
    """Casos de uso del equipo sobre los puertos de persistencia."""

    def __init__(
        self,
        *,
        equipment_repository: EquipmentRepository,
        device_types: CatalogRepository,
        brands: CatalogRepository,
        service_orders: ServiceOrderRepository,
        customers: CustomerRepository,
    ) -> None:
        self._equipment_repository = equipment_repository
        self._device_types = device_types
        self._brands = brands
        self._service_orders = service_orders
        self._customers = customers

    def create(
        self,
        *,
        device_type_id: int,
        brand_id: int,
        model: str,
        serial_number: str | None = None,
    ) -> EquipmentView:
        """Valida los maestros activos y delega el alta con su correlativo."""
        device_type = self._active_catalog_value(
            self._device_types, device_type_id, "device_type_id", "El tipo de dispositivo"
        )
        brand = self._active_catalog_value(self._brands, brand_id, "brand_id", "La marca")
        display_model = " ".join(model.split())
        if not display_model:
            raise ValidationError("model", "El modelo del equipo no puede estar vacío.")
        display_serial = serial_number.strip() if serial_number else None
        record = self._equipment_repository.create(
            device_type_id=device_type_id,
            brand_id=brand_id,
            model=display_model,
            serial_number=display_serial or None,
        )
        return EquipmentView(
            id=record.id,
            internal_code=record.internal_code,
            device_type=CatalogReference(id=device_type.id, name=device_type.name),
            brand=CatalogReference(id=brand.id, name=brand.name),
            model=record.model,
            serial_number=record.serial_number,
            created_at=record.created_at,
            current_owner=None,
            previous_services_count=0,
        )

    def lookup(
        self, *, internal_code: str | None = None, serial_number: str | None = None
    ) -> EquipmentView:
        """Identifica el equipo por código o serial, con precedencia del código (D-06)."""
        code = (internal_code or "").strip()
        serial = (serial_number or "").strip()
        if not code and not serial:
            raise ValidationError(
                "internal_code",
                "Indique el código interno o el número de serie del equipo.",
            )
        if code:
            record = self._equipment_repository.find_by_internal_code(code)
            if record is None:
                raise NotFoundError(EQUIPMENT_RESOURCE, code)
        else:
            record = self._equipment_repository.find_by_serial_number(serial)
            if record is None:
                raise NotFoundError(EQUIPMENT_RESOURCE, serial)
        return self._view(record)

    def _view(self, record: EquipmentRecord) -> EquipmentView:
        return EquipmentView(
            id=record.id,
            internal_code=record.internal_code,
            device_type=self._reference(self._device_types, record.device_type_id),
            brand=self._reference(self._brands, record.brand_id),
            model=record.model,
            serial_number=record.serial_number,
            created_at=record.created_at,
            current_owner=self._current_owner(record.id),
            previous_services_count=self._service_orders.count_for_equipment(record.id),
        )

    def _current_owner(self, equipment_id: int) -> CustomerReference | None:
        customer_id = self._service_orders.find_current_customer_id(equipment_id)
        if customer_id is None:
            return None
        customer = self._customers.get(customer_id)
        return None if customer is None else _customer_reference(customer)

    @staticmethod
    def _active_catalog_value(
        repository: CatalogRepository,
        catalog_id: int,
        field: str,
        label: str,
    ) -> CatalogValue:
        value = repository.get(catalog_id)
        if value is None or not value.is_active:
            raise ValidationError(field, f"{label} no existe o está inactivo.")
        return value

    @staticmethod
    def _reference(repository: CatalogRepository, catalog_id: int) -> CatalogReference:
        value = repository.get(catalog_id)
        return CatalogReference(id=catalog_id, name="" if value is None else value.name)


def _customer_reference(customer: CustomerRecord) -> CustomerReference:
    return CustomerReference(id=customer.id, name=customer.name, phone=customer.phone)
