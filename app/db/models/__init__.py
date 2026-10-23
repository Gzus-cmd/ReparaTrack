"""Modelos SQLAlchemy: cada submódulo declara sus tablas al importarse."""

from app.db.models.catalog import Brand, Component, DeviceType, OperationType
from app.db.models.customer import Customer
from app.db.models.equipment import CodeCounter, Equipment
from app.db.models.service_order import ServiceDetail, ServiceOrder
from app.db.models.state_history import StateHistory

__all__ = [
    "Brand",
    "CodeCounter",
    "Component",
    "Customer",
    "DeviceType",
    "Equipment",
    "OperationType",
    "ServiceDetail",
    "ServiceOrder",
    "StateHistory",
]
