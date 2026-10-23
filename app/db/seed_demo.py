"""Seeder de demostración con datos realistas para probar el sistema.

Puebla la base con clientes, equipos y servicios en distintos estados y edades
(para que el tablero, las alertas y la garantía se vean "vivos"), usando la
misma capa de servicios que la API, de modo que se respetan la máquina de
estados (RN-05), el correlativo de equipos (RN-02) y el mínimo de detalle
(RN-03).

Uso:
    py -m app.db.seed_demo          # resetea la base local y siembra los datos
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.api.deps import (
    build_customer_service,
    build_equipment_service,
    build_service_detail_service,
    build_service_order_service,
)
from app.config import Settings
from app.db.base import Base
from app.db.models.catalog import Brand, Component, DeviceType, OperationType
from app.db.models.service_order import ServiceOrder
from app.db.seed import seed_catalogs
from app.db.session import create_engine_from_url, create_session_factory

# --------------------------------------------------------------------------- #
# Datos realistas                                                             #
# --------------------------------------------------------------------------- #

CUSTOMERS = [
    ("María Fernández Quispe", "+51 987 123 456", "maria.fernandez@example.com", "44123456"),
    ("Jorge Huamán Torres", "+51 912 345 678", None, "47891234"),
    ("Rosa Cárdenas Linares", "+51 998 765 432", "rosa.cardenas@example.com", "40987654"),
    ("Luis Quispe Mamani", "+51 955 111 222", None, "45712345"),
    ("Ana Torres Salazar", "+51 933 444 555", "ana.torres@example.com", "45123456"),
    ("Carlos Rojas Vega", "+51 944 777 888", None, "46812345"),
    ("Patricia Salas Huerta", "+51 966 222 333", "patricia.salas@example.com", "47567891"),
    ("Diego Mendoza Paredes", "+51 977 888 999", None, "48901234"),
]

# (tipo de dispositivo, marca, modelo, número de serie)
EQUIPMENTS = [
    ("Laptop", "HP", "Pavilion 15", "5CD1234ABC"),
    ("Laptop", "Dell", "Latitude 5490", "8FT9876XYZ"),
    ("PC", "Lenovo", "ThinkCentre M720", "PC12345LEN"),
    ("Laptop", "Asus", "VivoBook 14", "ASB1412345"),
    ("PC", "HP", "ProDesk 400", "PHD4006789"),
    ("Impresora", "Epson", "EcoTank L3250", "EPSL3250001"),
    ("Laptop", "Acer", "Aspire 5", "ACER5A1234"),
    ("Impresora", "HP", "LaserJet M404", "HPLJ404001"),
    ("Laptop", "Apple", "MacBook Air M1", "MBA1123456"),
    ("PC", "Dell", "OptiPlex 3060", "OP3060DELL"),
]

FAILURES = [
    "No enciende",
    "Pantalla rota",
    "Muy lento al arrancar",
    "No imprime",
    "Se apaga solo",
    "Sobrecalienta",
    "El teclado no responde",
    "No carga la batería",
    "El ventilador hace mucho ruido",
    "No reconoce el disco",
]

CONDITIONS = [
    "Tornillo barrido en la tapa inferior",
    "Rayones leves en la carcasa",
    "En buen estado",
    "Bisagra floja",
]

# (operación, componente | None, descripción)
WORK_OPERATIONS = [
    ("Cambio", "Disco", "Se reemplazó el disco por un SSD de 512 GB."),
    ("Mantenimiento", "Pasta térmica", "Limpieza interna y cambio de pasta térmica."),
    ("Formateo", None, "Se reinstaló el sistema operativo desde cero."),
    ("Cambio", "Batería", "Se reemplazó la batería por una nueva."),
    ("Cambio", "Pad térmico", "Se reemplazó el pad térmico del disipador."),
    ("Reparación", "Teclado", "Se reparó el teclado y se limpiaron los contactos."),
]


class SeedClock:
    """Reloj controlable para fijar fechas realistas en el pasado."""

    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def set_to(self, moment: datetime) -> None:
        self._now = moment

    def advance(self, *, days: int = 0) -> None:
        self._now = self._now + timedelta(days=days)


def _catalog_ids(session: Session) -> dict[str, dict[str, int]]:
    """Índices `nombre -> id` de los cuatro maestros, ya normalizados por la semilla."""
    return {
        "device": {row.name: row.id for row in session.query(DeviceType).all()},
        "brand": {row.name: row.id for row in session.query(Brand).all()},
        "component": {row.name: row.id for row in session.query(Component).all()},
        "operation": {row.name: row.id for row in session.query(OperationType).all()},
    }


def seed_demo(session: Session) -> dict:
    """Siembra clientes, equipos y servicios realistas. Devuelve un resumen."""
    seed_catalogs(session)

    base_now = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    clock = SeedClock(base_now)
    ids = _catalog_ids(session)

    customers = build_customer_service(session)
    equipment_svc = build_equipment_service(session)
    orders = build_service_order_service(session, clock)
    details = build_service_detail_service(session)

    # 1) Clientes y equipos
    customer_records = [
        customers.create(name=name, phone=phone, email=email, document=document)
        for name, phone, email, document in CUSTOMERS
    ]
    equipment_views = [
        equipment_svc.create(
            device_type_id=ids["device"][device_type],
            brand_id=ids["brand"][brand],
            model=model,
            serial_number=serial,
        )
        for device_type, brand, model, serial in EQUIPMENTS
    ]

    def walk(equipment_index, customer_index, failure, condition, accessories, path, work):
        """Crea un servicio y recorre `path`: [(estado, días)], con RECEIVED primero."""
        equipment = equipment_views[equipment_index]
        customer = customer_records[customer_index]

        clock.set_to(base_now - timedelta(days=path[0][1]))
        order = orders.create(
            customer_id=customer.id,
            equipment_id=equipment.id,
            reported_failure=failure,
            accessories=accessories,
            physical_condition=condition,
            password_requested=(failure == "No enciende"),
        )

        for target, days_after in path[1:]:
            clock.advance(days=days_after)
            order = orders.transition(order.id, target=target, confirm=(target == "ABANDONED"))
            if target in ("AWAITING_APPROVAL", "AWAITING_PART", "NOT_REPARABLE"):
                details.add(
                    order.id,
                    operation_type_id=ids["operation"]["Diagnóstico"],
                    description="Se diagnosticó el equipo y se identificó la falla.",
                )
            elif target == "IN_REPAIR":
                for operation, component, description in work:
                    details.add(
                        order.id,
                        operation_type_id=ids["operation"][operation],
                        component_id=ids["component"].get(component),
                        description=description,
                    )
        return order

    # 2) Servicios en distintos estados y edades.
    FLOW = [
        ("DIAGNOSING", 1),
        ("AWAITING_APPROVAL", 1),
        ("IN_REPAIR", 1),
        ("READY_FOR_PICKUP", 1),
        ("DELIVERED", 1),
    ]

    work_change_disk = [WORK_OPERATIONS[0]]
    work_maintenance = [WORK_OPERATIONS[1]]
    work_format = [WORK_OPERATIONS[2]]
    work_battery = [WORK_OPERATIONS[3]]
    work_pad = [WORK_OPERATIONS[4]]
    work_keyboard = [WORK_OPERATIONS[5]]
    work_printer = [("Mantenimiento", None, "Se limpió el cabezal y se calibró la impresora.")]

    scenarios = [
        (0, 0, FAILURES[0], CONDITIONS[0], "Cargador", [("RECEIVED", 90)] + FLOW, work_maintenance),
        (
            1,
            1,
            FAILURES[2],
            CONDITIONS[2],
            "Cargador y mouse",
            [("RECEIVED", 45)] + FLOW,
            work_format,
        ),
        (
            2,
            2,
            FAILURES[4],
            CONDITIONS[2],
            "Cable de poder",
            [("RECEIVED", 5), ("DIAGNOSING", 1), ("AWAITING_APPROVAL", 1), ("IN_REPAIR", 1)],
            work_change_disk,
        ),
        (
            3,
            3,
            FAILURES[1],
            CONDITIONS[1],
            "Cargador",
            [
                ("RECEIVED", 6),
                ("DIAGNOSING", 1),
                ("AWAITING_APPROVAL", 1),
                ("IN_REPAIR", 1),
                ("READY_FOR_PICKUP", 1),
            ],
            work_pad,
        ),
        (
            4,
            4,
            FAILURES[5],
            CONDITIONS[2],
            "Cargador",
            [("RECEIVED", 10), ("DIAGNOSING", 1), ("AWAITING_APPROVAL", 1)],
            work_maintenance,
        ),
        (
            5,
            5,
            FAILURES[3],
            CONDITIONS[2],
            "Cable de poder",
            [("RECEIVED", 2), ("DIAGNOSING", 1), ("AWAITING_PART", 1)],
            work_battery,
        ),
        (
            6,
            6,
            FAILURES[6],
            CONDITIONS[3],
            "Cargador",
            [("RECEIVED", 1), ("DIAGNOSING", 1)],
            work_keyboard,
        ),
        (7, 7, FAILURES[7], CONDITIONS[2], "Sin cargador", [("RECEIVED", 0)], work_maintenance),
        (
            8,
            0,
            FAILURES[5],
            CONDITIONS[1],
            "Cargador",
            [("RECEIVED", 15), ("DIAGNOSING", 1), ("NOT_REPARABLE", 1), ("DELIVERED", 1)],
            work_maintenance,
        ),
        (
            9,
            1,
            FAILURES[2],
            CONDITIONS[2],
            "Cable de poder",
            [
                ("RECEIVED", 7),
                ("DIAGNOSING", 1),
                ("AWAITING_APPROVAL", 1),
                ("REJECTED", 1),
                ("DELIVERED", 1),
            ],
            work_format,
        ),
        (
            4,
            2,
            FAILURES[0],
            CONDITIONS[0],
            "Cargador",
            [
                ("RECEIVED", 200),
                ("DIAGNOSING", 1),
                ("AWAITING_APPROVAL", 1),
                ("IN_REPAIR", 2),
                ("READY_FOR_PICKUP", 1),
                ("ABANDONED", 181),
            ],
            work_change_disk,
        ),
        (
            6,
            3,
            FAILURES[6],
            CONDITIONS[3],
            "Cargador",
            [("RECEIVED", 40), ("DIAGNOSING", 1), ("AWAITING_APPROVAL", 1), ("ABANDONED", 31)],
            work_keyboard,
        ),
        # Casos extremos para demostración: terminales y fuera de umbral (RN-07 / RN-10).
        (
            9,
            2,
            FAILURES[0],
            CONDITIONS[0],
            "Cargador",
            [("RECEIVED", 12), ("DIAGNOSING", 1), ("NOT_REPARABLE", 1)],
            work_maintenance,
        ),
        (
            8,
            5,
            FAILURES[3],
            CONDITIONS[2],
            "Cable de poder",
            [("RECEIVED", 20), ("DIAGNOSING", 1), ("AWAITING_APPROVAL", 1), ("REJECTED", 1)],
            work_format,
        ),
        (
            5,
            6,
            FAILURES[3],
            CONDITIONS[2],
            "Cable de poder",
            [
                ("RECEIVED", 200),
                ("DIAGNOSING", 1),
                ("AWAITING_APPROVAL", 1),
                ("IN_REPAIR", 2),
                ("READY_FOR_PICKUP", 1),
            ],
            work_printer,
        ),
        (
            3,
            4,
            FAILURES[1],
            CONDITIONS[1],
            "Cargador",
            [("RECEIVED", 40), ("DIAGNOSING", 1), ("AWAITING_APPROVAL", 1)],
            work_pad,
        ),
    ]

    for scenario in scenarios:
        walk(*scenario)

    # 3) Reingreso en garantía: el equipo 0 reingresa 30 días después de la entrega.
    clock.set_to(base_now - timedelta(days=35))
    origin = orders.create(
        customer_id=customer_records[0].id,
        equipment_id=equipment_views[0].id,
        reported_failure="No enciende",
        accessories="Cargador",
        physical_condition=CONDITIONS[0],
    )
    for target in ("DIAGNOSING", "AWAITING_APPROVAL", "IN_REPAIR", "READY_FOR_PICKUP", "DELIVERED"):
        clock.advance(days=1)
        if target == "IN_REPAIR":
            details.add(
                origin.id,
                operation_type_id=ids["operation"]["Cambio"],
                component_id=ids["component"]["Batería"],
                description="Se reemplazó la batería.",
            )
        origin = orders.transition(origin.id, target=target)

    clock.set_to(base_now)
    orders.create(
        customer_id=customer_records[0].id,
        equipment_id=equipment_views[0].id,
        reported_failure="No enciende",
        accessories="Cargador",
        physical_condition=CONDITIONS[0],
        origin_service_id=origin.id,
    )

    session.flush()

    by_status = {
        status: session.query(ServiceOrder).filter_by(status=status).count()
        for status in (
            "RECEIVED",
            "DIAGNOSING",
            "AWAITING_APPROVAL",
            "AWAITING_PART",
            "IN_REPAIR",
            "NOT_REPARABLE",
            "REJECTED",
            "READY_FOR_PICKUP",
            "DELIVERED",
            "ABANDONED",
        )
    }

    return {
        "clientes": len(customer_records),
        "equipos": len(equipment_views),
        "servicios": sum(by_status.values()),
        "por_estado": by_status,
    }


def main() -> None:
    """Resetea la base local y la puebla con datos de demostración."""
    settings = Settings.from_env()
    engine = create_engine_from_url(settings.database_url)

    print(f"Base de datos: {settings.database_url}")
    print("Reseteando esquema y sembrando datos de demostración…")

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        summary = seed_demo(session)
        session.commit()

    print("\nDatos sembrados:")
    for key, value in summary.items():
        if key == "por_estado":
            print("  por estado:")
            for status, count in value.items():
                print(f"    {status:<18} {count}")
        else:
            print(f"  {key}: {value}")
    print("\nListo. Levantá la app para ver los datos.")


if __name__ == "__main__":
    main()
