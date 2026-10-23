# Plan Técnico — Sistema de Trazabilidad de Soporte Técnico (ReparaTrack)

**Versión:** 1.0 · **Fecha:** 22 de octubre de 2026
**Deriva de:** `00-constitucion.md` (v1.0) y `01-spec.md` (v1.0)
**Stack:** Python 3.14 · FastAPI · SQLAlchemy 2.x · SQLite · pytest + pytest-cov · Jinja2 · Ruff

> Este plan describe **estructura, modelo de datos, contrato y pruebas**. No contiene
> código de producción: solo definiciones descriptivas listas para convertirse en
> tareas TDD. Ante cualquier contradicción, manda la Constitución y luego la spec.

---

## 1. Arquitectura por capas

### 1.1 Capas y regla de dependencia

La dependencia apunta siempre hacia el dominio. Ninguna capa interna conoce a una
externa; la composición (wiring) ocurre únicamente en `app/main.py`.

| # | Capa | Responsabilidad | Puede importar | Artefactos | Se prueba con |
|---|---|---|---|---|---|
| 1 | **Dominio** (`app/domain`) | Máquina de estados, reglas RN-01…RN-10, cálculo de umbrales, generación del código correlativo, errores de negocio. Funciones y clases **puras**, sin I/O, sin `datetime.now()` implícito. | Solo biblioteca estándar (`enum`, `dataclasses`, `datetime`) | `enums.py`, `state_machine.py`, `rules.py`, `codes.py`, `errors.py` | Unitarias, sin fixtures de BD |
| 2 | **Servicios / aplicación** (`app/services`) | Orquestación de casos de uso: valida, consulta repositorios vía puertos, aplica reglas del dominio dentro de una transacción, registra historial. | `domain`, `services.ports` (protocolos) | `ports.py`, `catalog_service.py`, `customer_service.py`, `equipment_service.py`, `service_order_service.py`, `dashboard_service.py`, `warranty_service.py` | Unitarias con dobles de repositorio + integración |
| 3 | **API** (`app/api`) | Traducción HTTP ↔ servicios: routers FastAPI, esquemas Pydantic (request/response), manejo de errores de dominio a códigos HTTP, OpenAPI. Cero reglas de negocio. | `services`, `domain.enums`, `domain.errors` | `router.py`, `deps.py`, `errors.py`, `schemas/`, `routers/` | Integración con `TestClient` |
| 4 | **Persistencia** (`app/db`) | Modelos SQLAlchemy 2.x (`Mapped`/`mapped_column`), motor y sesiones, implementación concreta de los puertos (repositorios), datos semilla de maestros. | `domain.enums`, `services.ports` (implementa) | `base.py`, `session.py`, `models/`, `repositories/`, `seed.py` | Integración contra SQLite |
| 5 | **UI** (`app/web` + `app/templates`) | Renderizado Jinja2 responsive (celular y PC), formularios de recepción y transiciones, dashboard "equipos en taller". Consume los mismos servicios que la API. | `services` | `web/routes.py`, `web/view_models.py`, `templates/` | Humo (200 + contenido clave) |

**Reglas de dependencia obligatorias**

1. `domain` no importa nada de `app.*` salvo `app.domain.*`.
2. `services` no importa FastAPI, SQLAlchemy ni Jinja2. Declara lo que necesita en `ports.py`
   (protocolos: `CatalogRepository`, `CustomerRepository`, `EquipmentRepository`,
   `ServiceOrderRepository`, `StateHistoryRepository`, `Clock`).
3. `api` y `web` no tocan sesiones ni modelos SQLAlchemy; solo servicios y esquemas.
4. `db` es el único lugar con `Session`, `select()`, `commit()`.
5. Toda fecha "ahora" entra por el puerto `Clock`; el dominio recibe `datetime` como parámetro.

### 1.2 Flujo de una transición de estado (ejemplo: `IN_REPAIR → READY_FOR_PICKUP`)

1. `routers/service_orders.py` recibe `POST /service-orders/{id}/transitions` y valida el
   cuerpo con `TransitionRequest` (Pydantic).
2. `ServiceOrderService.transition(order_id, target, comment, confirm, actor_clock)` abre
   una transacción vía repositorio y carga la orden.
3. `domain.state_machine.can_transition(current, target)` verifica la matriz (RN-05);
   si es inválida lanza `InvalidTransitionError` **sin escribir nada**.
4. `domain.rules.ensure_ready_for_pickup_requirements(details_count, target)` aplica RN-03
   (≥ 1 detalle; "Diagnóstico" cuenta como operación válida).
5. Para destinos con umbral, `domain.rules.abandonment_eligibility(...)` calcula días
   desde la entrada al estado actual usando el historial (RN-07 / RN-10) y exige `confirm=True`.
6. El repositorio actualiza `service_orders.status` (y `delivered_at` si el destino es
   `DELIVERED`) y **añade** una fila en `state_history`. Ambos cambios en la misma transacción.
7. `errors.py` traduce `DomainError` → HTTP 409/422 con el envelope de error; el servicio
   devuelve `ServiceOrderRead` con `status`, `status_label` y `days_in_status`.

### 1.3 Estructura de carpetas

```text
reparatrack/
├── pyproject.toml                  # deps, pytest, ruff, coverage
├── README.md
├── .pre-commit-config.yaml         # ruff + pytest rápidos
├── .github/
│   └── workflows/ci.yml            # lint + tests en cada push (NFR-06)
├── app/
│   ├── __init__.py
│   ├── main.py                     # create_app(): routers, templates, handlers, seed
│   ├── config.py                   # Settings: DATABASE_URL, WARRANTY_DAYS, umbrales
│   ├── domain/                     # CAPA 1 — pura
│   │   ├── __init__.py
│   │   ├── enums.py                # ServiceStatus, y etiquetas en español
│   │   ├── state_machine.py        # matriz, can_transition, allowed_targets
│   │   ├── rules.py                # RN-03, RN-04, RN-07, RN-10, inmutabilidad
│   │   ├── codes.py                # formato del código interno correlativo
│   │   └── errors.py               # DomainError y subclases con `code`
│   ├── services/                   # CAPA 2 — aplicación
│   │   ├── __init__.py
│   │   ├── ports.py                # protocolos de repositorio + Clock
│   │   ├── catalog_service.py
│   │   ├── customer_service.py
│   │   ├── equipment_service.py
│   │   ├── service_order_service.py
│   │   ├── dashboard_service.py
│   │   └── warranty_service.py
│   ├── api/                        # CAPA 3 — HTTP
│   │   ├── __init__.py
│   │   ├── router.py               # agrega routers bajo /api/v1
│   │   ├── deps.py                 # get_session, get_service_*, get_clock
│   │   ├── errors.py               # DomainError -> JSON + status code
│   │   ├── schemas/
│   │   │   ├── common.py           # ErrorEnvelope, Page, StatusLabel
│   │   │   ├── catalogs.py
│   │   │   ├── customers.py
│   │   │   ├── equipment.py
│   │   │   ├── service_orders.py   # reception, details, transitions
│   │   │   └── dashboard.py
│   │   └── routers/
│   │       ├── health.py
│   │       ├── catalogs.py
│   │       ├── customers.py
│   │       ├── equipments.py
│   │       ├── service_orders.py
│   │       └── dashboard.py
│   ├── db/                         # CAPA 4 — persistencia
│   │   ├── __init__.py
│   │   ├── base.py                 # DeclarativeBase + metadata + naming convention
│   │   ├── session.py              # engine, SessionLocal, get_session()
│   │   ├── models/
│   │   │   ├── catalog.py          # DeviceType, Brand, Component, OperationType
│   │   │   ├── customer.py         # Customer
│   │   │   ├── equipment.py        # Equipment, CodeCounter
│   │   │   ├── service_order.py    # ServiceOrder, ServiceDetail
│   │   │   └── state_history.py    # StateHistory
│   │   ├── repositories/
│   │   │   ├── catalog_repository.py
│   │   │   ├── customer_repository.py
│   │   │   ├── equipment_repository.py
│   │   │   ├── service_order_repository.py
│   │   │   └── state_history_repository.py
│   │   └── seed.py                 # maestros base + "Diagnóstico" en operation_types
│   ├── web/                        # CAPA 5 — UI
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── view_models.py          # etiquetas ES, días transcurridos, badges
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── reception.html
│   │   ├── service_detail.html
│   │   ├── equipment_history.html
│   │   ├── catalogs.html
│   │   └── partials/               # estado_badge.html, detail_rows.html, error.html
│   └── static/
│       ├── css/app.css
│       └── js/app.js
└── tests/
    ├── conftest.py                 # app, engine, session, client, clock, factories
    ├── support/
    │   ├── clock.py                # FrozenClock (implementa el puerto Clock)
    │   └── factories.py            # build_*() de entidades persistidas
    ├── unit/
    │   └── domain/
    │       ├── test_state_machine.py
    │       ├── test_rules_details.py
    │       ├── test_rules_warranty.py
    │       ├── test_rules_abandonment.py
    │       ├── test_rules_immutability.py
    │       ├── test_catalog_rules.py
    │       ├── test_state_labels.py
    │       └── test_codes.py
    └── integration/
        ├── repositories/
        │   ├── test_catalog_repository.py
        │   └── test_service_order_repository.py
        └── api/
            ├── test_catalogs_api.py
            ├── test_customers_api.py
            ├── test_equipments_api.py
            ├── test_reception_api.py
            ├── test_details_api.py
            ├── test_transitions_api.py
            ├── test_dashboard_api.py
            ├── test_warranty_api.py
            ├── test_abandonment_api.py
            └── test_web_smoke.py
```

**Notas de estructura**

- No hay carpeta de migraciones en esta versión: el esquema se crea con `metadata.create_all()`
  al arrancar y en los tests. Si el modelo cambia después de la entrega, se evalúa Alembic
  como tarea aparte (fuera del alcance actual).
- `app/web` y `app/api` comparten servicios; ninguna regla se duplica en la UI.
- `static/js/app.js` es progresivo: la UI funciona sin JavaScript (formularios HTML).

---

## 2. Modelo de datos concreto

### 2.1 Decisión de nomenclatura (trazabilidad spec ↔ código)

La spec (§5) fija el **vocabulario de dominio** en español; la Constitución (§1.10) exige
**identificadores de código en inglés**. Se resuelve así: clases, tablas, columnas,
endpoints y funciones van en inglés; la correspondencia con la spec queda explícita en la
tabla de mapeo (2.10), y las etiquetas visibles al usuario van en español neutro.
Ningún atributo de la spec se pierde: todos aparecen mapeados.

Convenciones: SQLAlchemy 2.x declarativo (`Mapped[T]` / `mapped_column`), PK enteras
autoincrementales, `snake_case` en tablas y columnas, `DateTime(timezone=True)` en UTC,
`String` con longitud explícita, `Boolean` con `server_default`, enums como `VARCHAR` +
`CHECK` (`native_enum=False`, portable a SQLite).

### 2.2 Diagrama de relaciones

```text
device_types 1 ──< equipments >── 1 brands
                     │
                     │ 1
                     ▼ N
customers 1 ──< service_orders >── 1 equipments      (la propiedad vive AQUÍ, no en equipments)
                     │ 1                    ▲
                     ├──< service_details   │ self-FK (origin_service_id, nullable)
                     │        ├── 1 operation_types
                     │        └── 0..1 components
                     ├──< state_history
                     └──> service_orders (servicio de origen / garantía)
```

**Invariante estructural clave:** no existe `equipments.customer_id` ni tabla
`customer_equipments`. La relación Cliente–Equipo se registra por servicio (decisión
normalizada de la spec §5), de modo que un equipo vendido y reingresado por otra persona
conserva su historial técnico completo y se asocia al cliente del servicio vigente.

### 2.3 Maestros (RF-01, RN-09)

Los cuatro maestros comparten forma: `id`, `name` único, `is_active` para la baja lógica.
`seed.py` carga los valores base de la spec y, obligatoriamente, la operación **Diagnóstico**
en `operation_types` (RN-03).

**`device_types`** — TipoDispositivo

| Columna | Tipo | Nulo | Default | Restricciones |
|---|---|---|---|---|
| `id` | `Integer` | no | autoincrement | PK |
| `name` | `String(60)` | no | — | `UNIQUE`, `CHECK length(trim(name)) > 0` |
| `is_active` | `Boolean` | no | `true` | — |
| `created_at` | `DateTime(tz)` | no | `now(UTC)` | — |

**`brands`** — Marca

| Columna | Tipo | Nulo | Default | Restricciones |
|---|---|---|---|---|
| `id` | `Integer` | no | autoincrement | PK |
| `name` | `String(60)` | no | — | `UNIQUE`, no vacío |
| `is_active` | `Boolean` | no | `true` | — |
| `created_at` | `DateTime(tz)` | no | `now(UTC)` | — |

**`components`** — Componente (RAM, disco, pasta térmica, pad térmico…)

| Columna | Tipo | Nulo | Default | Restricciones |
|---|---|---|---|---|
| `id` | `Integer` | no | autoincrement | PK |
| `name` | `String(80)` | no | — | `UNIQUE`, no vacío |
| `is_active` | `Boolean` | no | `true` | — |
| `created_at` | `DateTime(tz)` | no | `now(UTC)` | — |

**`operation_types`** — TipoOperacion (mantenimiento, reparación, diagnóstico, cambio,
formateo, migración)

| Columna | Tipo | Nulo | Default | Restricciones |
|---|---|---|---|---|
| `id` | `Integer` | no | autoincrement | PK |
| `name` | `String(60)` | no | — | `UNIQUE`, no vacío |
| `is_active` | `Boolean` | no | `true` | — |
| `created_at` | `DateTime(tz)` | no | `now(UTC)` | — |

> RN-09: `DELETE` sobre un valor referenciado **no borra**; el servicio de catálogo responde
> con `catalog_value_in_use` y la baja se hace con `is_active = false`. La unicidad se
> evalúa sobre `name` normalizado (`trim` + `casefold`) para impedir duplicados por
> mayúsculas o espacios (RF-01).

### 2.4 `customers` — Cliente (RF-02)

| Columna | Tipo | Nulo | Default | Restricciones |
|---|---|---|---|---|
| `id` | `Integer` | no | autoincrement | PK |
| `name` | `String(120)` | no | — | no vacío |
| `phone` | `String(30)` | no | — | no vacío (contacto mínimo) |
| `email` | `String(120)` | sí | `NULL` | formato de correo si viene |
| `document` | `String(20)` | sí | `NULL` | `UNIQUE` cuando no es `NULL` (dato diferenciador) |
| `created_at` | `DateTime(tz)` | no | `now(UTC)` | — |

Índices: `ix_customers_name` (búsqueda por nombre), `ix_customers_phone`.

### 2.5 `equipments` — Equipo (RF-03, RN-02)

| Columna | Tipo | Nulo | Default | Restricciones |
|---|---|---|---|---|
| `id` | `Integer` | no | autoincrement | PK |
| `internal_code` | `String(12)` | no | generado | `UNIQUE`, formato `EQ-` + 6 dígitos (`EQ-000001`) |
| `device_type_id` | `Integer` | no | — | `FK device_types.id`, `ON DELETE RESTRICT` |
| `brand_id` | `Integer` | no | — | `FK brands.id`, `ON DELETE RESTRICT` |
| `model` | `String(120)` | no | — | no vacío |
| `serial_number` | `String(120)` | **sí** | `NULL` | sin `UNIQUE` (el serial puede repetirse o faltar) |
| `created_at` | `DateTime(tz)` | no | `now(UTC)` | — |

Índices: `ux_equipments_internal_code` (`UNIQUE`), `ix_equipments_serial_number`.

**Generación del código correlativo.** Tabla auxiliar `code_counters` con una fila por
secuencia; `equipment_service` ejecuta `UPDATE code_counters SET last_value = last_value + 1
WHERE name = 'equipment'` dentro de la misma transacción y formatea
`EQ-{last_value:06d}`. Ventajas: no depende del `id` (evita reutilización de códigos
tras un borrado), es atómico y deja el formato en `domain/codes.py`, que es puro y testeable.

**`code_counters`**

| Columna | Tipo | Nulo | Default | Restricciones |
|---|---|---|---|---|
| `name` | `String(40)` | no | — | PK (`'equipment'`) |
| `last_value` | `Integer` | no | `0` | `CHECK last_value >= 0` |

**Prohibido:** `equipments.customer_id`. El dueño vigente se obtiene desde el último
`service_orders.customer_id` del equipo.

### 2.6 `service_orders` — Servicio (RF-04, RF-06, RF-09, RF-10)

| Columna | Tipo | Nulo | Default | Restricciones |
|---|---|---|---|---|
| `id` | `Integer` | no | autoincrement | PK |
| `equipment_id` | `Integer` | no | — | `FK equipments.id`, `ON DELETE RESTRICT` (RN-01: un servicio = un equipo) |
| `customer_id` | `Integer` | no | — | `FK customers.id`, `ON DELETE RESTRICT` |
| `received_at` | `DateTime(tz)` | no | `now(UTC)` | fecha/hora de recepción (RF-04) |
| `reported_failure` | `String(500)` | no | — | no vacío (campo obligatorio, RF-04) |
| `physical_condition` | `String(500)` | no | — | **inmutable** (RN-08) |
| `accessories` | `String(500)` | no | — | inventario textual de lo recibido (puede ser "ninguno") |
| `password_requested` | `Boolean` | no | `false` | RN-06: solo el indicador, nunca el valor |
| `status` | `Enum(ServiceStatus)` (`VARCHAR(24)`) | no | `RECEIVED` | `CHECK status IN (...)` con los 10 valores |
| `delivered_at` | `DateTime(tz)` | sí | `NULL` | obligatorio si `status = DELIVERED` (`CHECK`) |
| `origin_service_id` | `Integer` | **sí** | `NULL` | FK autorreferente `service_orders.id`, `ON DELETE SET NULL` (garantía) |
| `created_at` | `DateTime(tz)` | no | `now(UTC)` | — |
| `updated_at` | `DateTime(tz)` | no | `now(UTC)` on update | — |

Restricciones adicionales:

- `CHECK origin_service_id <> id` (un servicio no se origina en sí mismo).
- `CHECK (status = 'DELIVERED') = (delivered_at IS NOT NULL)` — coherencia estado/fecha.
- `UNIQUE (origin_service_id)` — un servicio de origen admite **un** reingreso vinculado;
  un segundo reingreso exige decidir cuál es el antecedente (el técnico elige, RN-04).

Índices: `ix_service_orders_status`, `ix_service_orders_equipment_id`,
`ix_service_orders_customer_id`, `ix_service_orders_received_at`,
`ix_service_orders_status_received` (dashboard: estado + antigüedad).

### 2.7 `service_details` — DetalleServicio (RF-05, RN-03)

| Columna | Tipo | Nulo | Default | Restricciones |
|---|---|---|---|---|
| `id` | `Integer` | no | autoincrement | PK |
| `service_order_id` | `Integer` | no | — | `FK service_orders.id`, `ON DELETE CASCADE` |
| `operation_type_id` | `Integer` | no | — | `FK operation_types.id`, `ON DELETE RESTRICT` |
| `component_id` | `Integer` | **sí** | `NULL` | `FK components.id`, `ON DELETE RESTRICT` (opcional: un formateo no usa componente) |
| `description` | `String(500)` | no | — | no vacío |
| `created_at` | `DateTime(tz)` | no | `now(UTC)` | — |

Índice: `ix_service_details_service_order_id`. No hay `UNIQUE` sobre la combinación
operación/componente: dos cambios de RAM en el mismo servicio son líneas distintas.

> RN-03 se aplica en la **transición**, no en la base: la orden puede vivir en `IN_REPAIR`
> con cero detalles y solo se bloquea al intentar `READY_FOR_PICKUP`. "Diagnóstico" es un
> `operation_types.name` sembrado, no un caso especial en el código: una línea con esa
> operación satisface el mínimo (cierra el flujo de rechazo sin falsear datos).

### 2.8 `state_history` — HistorialEstado (RF-06, RN-05)

Tabla **append-only**: solo `INSERT`. Sin `UPDATE` ni `DELETE` expuestos; el repositorio
no publica métodos de mutación.

| Columna | Tipo | Nulo | Default | Restricciones |
|---|---|---|---|---|
| `id` | `Integer` | no | autoincrement | PK |
| `service_order_id` | `Integer` | no | — | `FK service_orders.id`, `ON DELETE CASCADE` |
| `status` | `Enum(ServiceStatus)` | no | — | estado **alcanzado** (uno de los 10) |
| `changed_at` | `DateTime(tz)` | no | `now(UTC)` | fecha y hora del cambio |
| `comment` | `String(500)` | **sí** | `NULL` | motivo / observación (opcional) |

Índices: `ix_state_history_service_status` (`service_order_id`, `status`, `changed_at`),
`ix_state_history_changed_at`.

Reglas de la bitácora:

1. Al crear la orden se inserta la fila inicial `RECEIVED` en la **misma** transacción; el
   historial nunca está vacío.
2. Cada transición añade exactamente una fila con el estado destino.
3. La "fecha de entrada al estado actual" es `max(changed_at)` de las filas con
   `status = estado_actual`; de ahí se calculan los umbrales de 30 y 180 días (2.9).
4. No se permite insertar una fila cuyo estado no sea alcanzable desde el anterior: lo
   garantiza el servicio y lo verifica un test de integración sobre el historial completo.

### 2.9 Estados, etiquetas y umbrales

| Clave (código/API) | Etiqueta ES (UI) | Terminal | Umbral asociado |
|---|---|---|---|
| `RECEIVED` | Recibido | no | — |
| `DIAGNOSING` | En diagnóstico | no | — |
| `AWAITING_APPROVAL` | Esperando aprobación | no | RN-10: ≥ 30 días → `ABANDONED` |
| `AWAITING_PART` | Esperando repuesto | no | — |
| `IN_REPAIR` | En reparación | no | — |
| `NOT_REPARABLE` | No reparable | no | — |
| `REJECTED` | Rechazado | no | — |
| `READY_FOR_PICKUP` | Listo para entrega | no | RN-07: > 180 días → `ABANDONED` |
| `DELIVERED` | Entregado | **sí** | RN-04: garantía 90 días desde `delivered_at` |
| `ABANDONED` | Abandonado | **sí** | — |

Matriz cerrada (RN-05) con guardas:

| Origen | Destinos válidos | Guarda adicional |
|---|---|---|
| `RECEIVED` | `DIAGNOSING` | — |
| `DIAGNOSING` | `AWAITING_APPROVAL`, `AWAITING_PART`, `NOT_REPARABLE` | — |
| `AWAITING_APPROVAL` | `IN_REPAIR`, `REJECTED`, `ABANDONED` | `ABANDONED`: días en el estado ≥ 30 **y** `confirm = true` |
| `AWAITING_PART` | `IN_REPAIR` | — |
| `IN_REPAIR` | `READY_FOR_PICKUP`, `AWAITING_PART` | `READY_FOR_PICKUP`: ≥ 1 detalle (RN-03) |
| `NOT_REPARABLE` | `DELIVERED` | fija `delivered_at` |
| `REJECTED` | `DELIVERED` | fija `delivered_at` |
| `READY_FOR_PICKUP` | `DELIVERED`, `ABANDONED`, `IN_REPAIR` | `ABANDONED`: días > 180 y `confirm = true`; `IN_REPAIR`: retrabajo, sin guarda de umbral |
| `DELIVERED` | — (terminal) | reingreso = **nuevo** servicio con `origin_service_id` |
| `ABANDONED` | — (terminal) | — |

Reglas temporales (funciones puras, reciben `as_of`):

| Regla | Expresión | Frontera (spec) | Casos de prueba |
|---|---|---|---|
| RN-04 garantía | `days_since(delivered_at) < 90` → candidato a vincular; `>= 90` → servicio nuevo | 89 sí / 90 no / 91 no | 89, 90, 91 |
| RN-10 abandono por aprobación | `days_in(AWAITING_APPROVAL) >= 30` | "tras 30 días", día 30 ya habilita | 29, 30, 31 |
| RN-07 abandono por retiro | `days_in(READY_FOR_PICKUP) > 180` | "supera 180 días", día 180 todavía no | 179, 180, 181 |

> Asimetría deliberada: la spec dice "tras 30 días" (inclusivo) y "supera 180 días"
> (estrictamente mayor). Se codifica tal cual y se fija con tests de frontera, sin
> redondear ninguna de las dos.

Los días se calculan sobre **fecha calendario de negocio** en `America/Lima`
(`ZoneInfo`), aunque se persista UTC: evita el desfase de un día en los umbrales.

### 2.10 Mapeo spec §5 → código

| Término / atributo en spec | Clase SQLAlchemy | Tabla | Columna |
|---|---|---|---|
| TipoDispositivo | `DeviceType` | `device_types` | `id`, `name` (`nombre`) |
| Marca | `Brand` | `brands` | `id`, `name` (`nombre`) |
| Componente | `Component` | `components` | `id`, `name` (`nombre`) |
| TipoOperacion | `OperationType` | `operation_types` | `id`, `name` (`nombre`) |
| Cliente | `Customer` | `customers` | `id`, `name`, `phone`, `email`, `document` |
| Equipo | `Equipment` | `equipments` | `id`, `internal_code` (`codigo_interno`), `device_type_id`, `brand_id`, `model`, `serial_number` |
| Servicio | `ServiceOrder` | `service_orders` | `id`, `equipment_id`, `customer_id`, `received_at` (`fecha_recepcion`), `reported_failure` (`falla_reportada`), `physical_condition` (`condicion_fisica`), `accessories` (`accesorios`), `password_requested` (`contrasena_solicitada`), `status` (`estado`), `delivered_at` (`fecha_entrega`), `origin_service_id` (`servicio_origen_id`) |
| DetalleServicio | `ServiceDetail` | `service_details` | `id`, `service_order_id`, `operation_type_id`, `component_id`, `description` |
| HistorialEstado | `StateHistory` | `state_history` | `id`, `service_order_id`, `status` (`estado`), `changed_at` (`fecha_hora`), `comment` (`comentario`) |

### 2.11 Invariantes y su punto de aplicación

| Invariante | Dominio | Servicio | Base de datos |
|---|---|---|---|
| Equipo sin dueño (relación por servicio) | — | — | Ausencia de `equipments.customer_id` (verificado por test de metadatos) |
| Código interno único y correlativo (RN-02) | `codes.format_internal_code` | `EquipmentService.create` | `UNIQUE` + `code_counters` |
| Serial opcional | — | validación laxa | `NULL` permitido |
| Condición física inmutable (RN-08) | `rules.assert_condition_immutable` | esquema de update la prohíbe | listener `before_flush` |
| ≥ 1 detalle para `READY_FOR_PICKUP` (RN-03) | `rules.ensure_details_for_pickup` | `ServiceOrderService.transition` | — |
| Transiciones cerradas (RN-05) | `state_machine.can_transition` | `transition` | `CHECK status IN (...)` |
| Historial completo y append-only (RN-05) | — | `transition` inserta la fila | tabla sin ruta de `UPDATE`/`DELETE` |
| Cero contraseñas (RN-06) | — | solo `bool` | ausencia de columna de contraseña |
| Maestro en uso se desactiva (RN-09) | — | `CatalogService.delete` | `RESTRICT` en FKs |

**Inmutabilidad de `physical_condition` — tres barreras:** (1) no existe endpoint que la
reciba en un `PATCH`; (2) el esquema Pydantic de actualización usa `extra="forbid"` y
responde `422 immutable_field`; (3) un listener `before_flush` de SQLAlchemy compara el
valor histórico y lanza `ImmutableFieldError` si cambió, atajando cualquier vía futura.

---

## 3. Contrato de API REST

**Base:** `/api/v1` (FastAPI + SQLite; Swagger en `/docs`, obligatorio por DoD).
**Formato:** JSON UTF-8. Fechas ISO-8601 con zona (`2026-10-22T15:04:05Z`).
**Sin autenticación** (fuera de alcance, spec §2).

**Envelope de error** (uniforme, mensajes en español neutro):

| Campo | Tipo | Descripción |
|---|---|---|
| `error.code` | `string` | Código estable en inglés (`invalid_transition`, `catalog_duplicate`, …) |
| `error.message` | `string` | Mensaje legible en español para la UI |
| `error.details` | `object` | Contexto: `field`, `from_status`, `to_status`, `days_in_status`, etc. |

**Códigos HTTP:** `200` lectura/transición, `201` creación, `204` baja física,
`404` recurso inexistente, `409` conflicto de negocio/estado, `422` validación de entrada
(incluye el campo faltante, RF-04), `405` método no permitido.

### 3.1 RF-01 — Maestros (4 recursos simétricos)

`{catalog}` ∈ `device-types` · `brands` · `components` · `operation-types`

| Método | Ruta | Descripción | Request | Response |
|---|---|---|---|---|
| `GET` | `/catalogs/{catalog}?active=true` | Lista valores; por defecto solo activos | query `active` (`bool`, opcional) | `200` `CatalogValueRead[]` (`id`, `name`, `is_active`, `in_use`) |
| `GET` | `/catalogs/{catalog}/{id}` | Obtiene un valor | — | `200` `CatalogValueRead` / `404` |
| `POST` | `/catalogs/{catalog}` | Crea valor; **rechaza duplicados** normalizados | `{"name": "..."}` | `201` `CatalogValueRead` / `409 catalog_duplicate` |
| `PATCH` | `/catalogs/{catalog}/{id}` | Renombra (valida duplicado) | `{"name": "..."}` | `200` / `409 catalog_duplicate` |
| `POST` | `/catalogs/{catalog}/{id}/deactivate` | Baja lógica (idempotente) | — | `200` `CatalogValueRead` con `is_active=false` |
| `POST` | `/catalogs/{catalog}/{id}/activate` | Reactiva | — | `200` |
| `DELETE` | `/catalogs/{catalog}/{id}` | Borra solo si **no está en uso** | — | `204` / `409 catalog_value_in_use` (con `hint` al endpoint de baja) |

> RF-01 literal: "dado un valor en uso, cuando intento eliminarlo, entonces se desactiva
> en vez de borrar". Se implementa con `DELETE` que responde `409` + `details.hint` y un
> endpoint explícito de baja lógica; el test cubre ambos caminos.

### 3.2 RF-02 — Clientes

| Método | Ruta | Descripción | Request | Response |
|---|---|---|---|---|
| `GET` | `/customers?q=&limit=&offset=` | Busca por nombre, teléfono o documento | query | `200` `{items, total}` |
| `GET` | `/customers/{id}` | Ficha del cliente | — | `200` `CustomerRead` / `404` |
| `POST` | `/customers` | Registra cliente con su contacto | `name`, `phone`, `email?`, `document?` | `201` `CustomerRead` / `409 document_duplicate` |
| `PATCH` | `/customers/{id}` | Actualiza contacto | campos opcionales | `200` / `404` |
| `GET` | `/customers/{id}/history` | Servicios del cliente (RF-08) | query `from`/`to` | `200` `ServiceOrderSummary[]` |

### 3.3 RF-03 — Equipos

| Método | Ruta | Descripción | Request | Response |
|---|---|---|---|---|
| `POST` | `/equipments` | Crea equipo y **genera código interno correlativo** | `device_type_id`, `brand_id`, `model`, `serial_number?` | `201` `EquipmentRead` (incluye `internal_code`) / `422 validation_error` |
| `GET` | `/equipments/{id}` | Ficha del equipo | — | `200` `EquipmentRead` / `404` |
| `GET` | `/equipments/lookup?internal_code=&serial_number=` | Busca por código **o** serial conocido | al menos un parámetro | `200` `EquipmentRead` + `previous_services_count` / `404` |
| `GET` | `/equipments/{id}/history` | Historial técnico completo (RF-08): servicios, estados y detalles | query `include=details,states` | `200` `EquipmentHistoryRead` |

`EquipmentRead`: `id`, `internal_code`, `device_type{id,name}`, `brand{id,name}`, `model`,
`serial_number`, `created_at`, `current_owner` (último cliente con servicio, derivado).

### 3.4 RF-04 — Recepción

| Método | Ruta | Descripción | Request | Response |
|---|---|---|---|---|
| `POST` | `/service-orders` | Crea el servicio en `RECEIVED` con fecha/hora y la primera fila de historial | ver tabla siguiente | `201` `ServiceOrderRead` / `422` con `details.field` / `409 warranty_expired` (si se envía `origin_service_id` inválido) |

Cuerpo de recepción:

| Campo | Tipo | Obligatorio | Nota |
|---|---|---|---|
| `customer_id` | `int` | sí (1/5) | Cliente existente |
| `equipment_id` | `int` | sí (2/5) | XOR con `new_equipment` |
| `new_equipment` | `object` | sí (2/5) | `{device_type_id, brand_id, model, serial_number?}`; crea el equipo en la misma transacción (recepción ≤ 2 min, NFR-01) |
| `reported_failure` | `string(1..500)` | sí (3/5) | Sin este campo → `422` indicando `reported_failure` |
| `accessories` | `string(1..500)` | sí (4/5) | "ninguno" es un valor válido |
| `physical_condition` | `string(1..500)` | sí (5/5) | Se fija aquí y **nunca** se edita (RN-08) |
| `password_requested` | `bool` | no | Default `false`; solo el indicador (RN-06) |
| `origin_service_id` | `int` | no | Vínculo de garantía (RF-09), validado en 3.8 |

Regla `equipment_id` XOR `new_equipment`: exactamente uno; ambos o ninguno → `422`
`equipment_source_invalid`.

### 3.5 RF-05 — Operaciones / detalle

| Método | Ruta | Descripción | Request | Response |
|---|---|---|---|---|
| `GET` | `/service-orders/{id}/details` | Líneas registradas | — | `200` `ServiceDetailRead[]` |
| `POST` | `/service-orders/{id}/details` | Registra operación con componente opcional | `operation_type_id`, `component_id?`, `description` | `201` `ServiceDetailRead` / `409 service_order_terminal` |
| `DELETE` | `/service-orders/{id}/details/{detail_id}` | Corrige una línea mal cargada | — | `204` / `409 service_order_terminal` / `404` |

`ServiceOrderRead` incluye `details_count`, de modo que la UI anticipa si
`READY_FOR_PICKUP` está habilitado (RN-03).

### 3.6 RF-06 — Estados e historial

| Método | Ruta | Descripción | Request | Response |
|---|---|---|---|---|
| `GET` | `/service-orders/{id}` | Ficha completa con estado y días | — | `200` `ServiceOrderRead` / `404` |
| `GET` | `/service-orders?status=&customer_id=&equipment_id=` | Bandeja filtrable | query + paginación | `200` `{items, total}` |
| `POST` | `/service-orders/{id}/transitions` | Ejecuta una transición válida y **registra historial** | `{to_status, comment?, confirm?}` | `200` `ServiceOrderRead` / `409 invalid_transition` / `409 details_required` / `409 threshold_not_reached` / `409 confirmation_required` / `422 unknown_status` |
| `GET` | `/service-orders/{id}/transitions` | Estados permitidos ahora (con guardas evaluadas) | — | `200` `{current, allowed: [{to_status, status_label, blocked_reason?}]}` |
| `GET` | `/service-orders/{id}/history` | Bitácora inmutable ordenada por `changed_at` | — | `200` `StateHistoryRead[]` |

`ServiceOrderRead`: `id`, `equipment{id, internal_code, model}`,
`customer{id, name, phone}`, `status`, `status_label`, `received_at`, `delivered_at`,
`days_in_status`, `days_since_reception`, `details_count`, `password_requested`,
`origin_service_id`, `allowed_transitions`.

Errores de transición con contexto explícito:

| Caso | HTTP | `error.code` | `details` |
|---|---|---|---|
| Par no permitido por la matriz | `409` | `invalid_transition` | `from_status`, `to_status`, `allowed` |
| `READY_FOR_PICKUP` sin detalles | `409` | `details_required` | `details_count: 0` |
| `ABANDONED` sin umbral cumplido | `409` | `threshold_not_reached` | `rule: "RN-10"` o `"RN-07"`, `days_in_status`, `required_days` |
| `ABANDONED` sin `confirm=true` | `409` | `confirmation_required` | `to_status` |

> En los cuatro casos el estado **no cambia** y no se inserta fila de historial: es el
> criterio central de RF-06 y se verifica en integración comparando estado + conteo de
> historial antes y después.

### 3.7 RF-07 — Dashboard "equipos en taller"

| Método | Ruta | Descripción | Request | Response |
|---|---|---|---|---|
| `GET` | `/dashboard/workbench?status=&sort=days_desc` | Servicios sin entregar con cliente, estado y días transcurridos | query opcional | `200` `WorkbenchRead` |
| `GET` | `/dashboard/summary` | Conteo por estado + alertas de umbral | — | `200` `{by_status: {...}, alerts: {...}}` |

`WorkbenchRead.items[]`: `service_order_id`, `customer_name`, `equipment_internal_code`,
`device_type`, `status`, `status_label`, `days_since_reception`, `days_in_status`,
`is_over_threshold`, `threshold_rule` (`RN-07`/`RN-10`/`null`).
Excluye `DELIVERED` y `ABANDONED` (no están "en taller").

### 3.8 RF-09 — Garantía y reingreso

| Método | Ruta | Descripción | Request | Response |
|---|---|---|---|---|
| `GET` | `/warranty/candidates?equipment_id=&as_of=` | Servicios entregados hace **< 90 días** para ofrecer vinculación | query | `200` `WarrantyCandidate[]` (`service_order_id`, `delivered_at`, `days_since_delivery`, `warranty_days_left`, `reported_failure`) |
| `GET` | `/warranty/eligibility?origin_service_id=&as_of=` | Evalúa un origen concreto | query | `200` `{eligible, days_since_delivery, reason}` |
| `POST` | `/service-orders` con `origin_service_id` | Vincula el reingreso al servicio original | ver 3.4 | `201` con `origin_service_id` / `409 warranty_expired` u `409 origin_not_delivered` |

Validaciones del vínculo: el origen debe existir, estar `DELIVERED`, pertenecer al **mismo
`equipment_id`**, tener `days_since_delivery < 90` y no tener ya un reingreso vinculado.
`>= 90` días → `409 warranty_expired` y la UI obliga a crear un servicio nuevo (RF-09).
El sistema **alerta**; el técnico **decide** si es "misma falla" (RN-04): no se compara
texto de fallas ni se bloquea por diferencia de redacción.

### 3.9 RF-10 — Abandono

| Método | Ruta | Descripción | Request | Response |
|---|---|---|---|---|
| `GET` | `/abandonment/candidates?rule=` | Identifica servicios que superan el umbral; `rule` acepta `RN-07` o `RN-10` (si se omite, devuelve ambos grupos) | query opcional | `200` `AbandonmentCandidate[]` (`service_order_id`, `status`, `days_in_status`, `threshold_days`, `rule`, `customer_name`, `equipment_internal_code`) |
| `POST` | `/service-orders/{id}/transitions` → `ABANDONED` | Marca abandono **con confirmación explícita** | `{to_status: "ABANDONED", confirm: true, comment?}` | `200` / `409 threshold_not_reached` / `409 confirmation_required` |

Dos grupos, nunca mezclados: `AWAITING_APPROVAL` con ≥ 30 días (RN-10) y
`READY_FOR_PICKUP` con > 180 días (RN-07). La transición es manual y confirmada; no hay
job automático en el alcance (la spec dice "puede marcarse" / "se marca" al consultar).

### 3.10 Endpoints de UI (Jinja2, HTML)

| Método | Ruta | Vista |
|---|---|---|
| `GET` | `/` | Dashboard "equipos en taller" (responsive, NFR-02) |
| `GET` | `/reception` · `POST /reception` | Formulario de recepción de 5 campos (NFR-01) |
| `GET` | `/service-orders/{id}` | Ficha con historial, detalles y botones de transición permitidos |
| `POST` | `/service-orders/{id}/transitions` | Envía la transición y redirige con mensaje en español |
| `GET` | `/equipments/{id}/history` | Historial completo del equipo (RF-08) |
| `GET` | `/catalogs` | Administración de maestros (RF-01) |

Las vistas consumen los servicios, no la API HTTP: misma lógica, sin duplicar reglas.

---

## 4. Estrategia de pruebas

### 4.1 Pirámide y objetivos

| Nivel | Alcance | Herramientas | Cantidad objetivo | Tiempo |
|---|---|---|---|---|
| Unitarias | `app/domain` (máquina de estados, reglas, códigos) | pytest puro, `pytest.mark.parametrize` | ~60 casos | < 2 s |
| Integración | Repositorios + API con `TestClient` contra SQLite | pytest + FastAPI `TestClient` | ~45 casos | < 30 s |
| Humo UI | Vistas Jinja2 (200 + contenido clave) | `TestClient` sobre `app/web` | ~6 casos | < 5 s |

Cobertura (DoD): **≥ 80 %** en `app/domain` y `app/services`, medido con
`pytest-cov` y `--cov-branch`. `app/api/schemas`, `app/db/models` y `app/templates`
se reportan pero no son la puerta de calidad.

### 4.2 Pruebas unitarias (dominio puro, sin BD ni reloj real)

| Módulo | Archivo | Casos exigidos |
|---|---|---|
| Máquina de estados | `tests/unit/domain/test_state_machine.py` | Las **15** aristas válidas de la matriz (parametrizadas, una por par) → `True`; una muestra exhaustiva de pares inválidos (todas las combinaciones `10×10` menos las válidas) → `raise InvalidTransitionError`; estados terminales (`DELIVERED`, `ABANDONED`) sin salidas; **`READY_FOR_PICKUP → IN_REPAIR` permitido** (retrabajo); `allowed_targets(status)` coincide con la matriz; el mensaje de error nombra origen y destino |
| RN-03 detalle mínimo | `test_rules_details.py` | `0` detalles → bloquea `READY_FOR_PICKUP`; `1` → permite; `5` → permite; la regla **no** bloquea otros destinos (`IN_REPAIR`, `AWAITING_PART`); una línea con operación "Diagnóstico" **cuenta** como válida; el chequeo no mira el texto de la descripción |
| RN-04 garantía | `test_rules_warranty.py` | `days_since_delivery` = 89 → candidato, `warranty_days_left = 1`; 90 → no elegible; 91 → no elegible; 0 → elegible; origen no `DELIVERED` → no elegible; servicio nuevo sin origen no consulta garantía |
| RN-07 abandono por retiro | `test_rules_abandonment.py` | `days_in(READY_FOR_PICKUP)` 179 y 180 → no elegible; 181 → elegible; `confirm=False` → `ConfirmationRequired`; desde otro estado la regla no aplica |
| RN-10 abandono por aprobación | idem | 29 → no elegible; 30 → elegible; 31 → elegible; `confirm=False` → bloquea; `ABANDONED` desde `AWAITING_APPROVAL` es la única ruta por esta regla |
| RN-08 inmutabilidad | `test_rules_immutability.py` | Mismo valor → permitido (no-op); valor distinto → `ImmutableFieldError`; `None` sobre valor previo → error; la función no muta la entrada |
| Código correlativo (RN-02) | `test_codes.py` | `1 → "EQ-000001"`, `42 → "EQ-000042"`, `999999 → "EQ-999999"`; ancho fijo de 6; rechazo de valores `<= 0`; el formato no depende del `id` de la fila |
| Duplicados de maestros (RF-01) | `test_catalog_rules.py` (movido a unit con doble de repositorio) | `"RAM"` vs `" ram "` → duplicado; distinta capitalización → duplicado; nombre vacío o solo espacios → `ValidationError`; valor inactivo con el mismo nombre → también se rechaza |
| Etiquetas de estado | `test_state_labels.py` | Los 10 estados tienen etiqueta en español; no hay claves duplicadas ni etiquetas vacías; `ServiceStatus` tiene exactamente 10 miembros |

Criterios de escritura: cada test recibe fechas explícitas (nunca `datetime.now()`),
usa `pytest.mark.parametrize` para las fronteras y asserta el **tipo de error y su
`code`**, no el texto completo (los mensajes pueden mejorar sin romper tests).

### 4.3 Pruebas de integración (repositorio + API con `TestClient`)

| Área | Archivo | Casos exigidos |
|---|---|---|
| Catálogos (RF-01) | `test_catalogs_api.py` | Crear valor → `201`; duplicado exacto y con espacios/mayúsculas → `409 catalog_duplicate`; `DELETE` sin uso → `204` y desaparece del listado; `DELETE` en uso → `409 catalog_value_in_use` y el valor sigue existiendo; baja lógica → deja de aparecer con `active=true` pero sigue en la BD |
| Clientes (RF-02) | `test_customers_api.py` | Alta con contacto → `201`; falta `phone` → `422` con `details.field`; documento duplicado → `409`; búsqueda `q` encuentra por nombre y por teléfono |
| Equipos (RF-03) | `test_equipments_api.py` | Alta genera `EQ-000001`, luego `EQ-000002` (correlativo sin huecos); `serial_number` omitido → `201` con `null`; `lookup` por código y por serial devuelve el equipo con `previous_services_count`; código inexistente → `404`; verificación estructural: `equipments` **no** tiene columna `customer_id` (`inspect(engine).get_columns`) |
| Recepción (RF-04) | `test_reception_api.py` | Recepción completa → `201`, `status = RECEIVED`, `received_at` presente, `1` fila `RECEIVED` en historial; sin `reported_failure` → `422` con `details.field = "reported_failure"` y **cero** servicios creados; `equipment_id` + `new_equipment` a la vez → `422 equipment_source_invalid`; `new_equipment` crea el equipo y devuelve su `internal_code`; `password_requested` por defecto `false`; el response **no** contiene ningún campo de contraseña |
| Detalles (RF-05) | `test_details_api.py` | Alta de línea con componente → `201`; sin componente (formateo) → `201`; `details_count` sube en `GET /service-orders/{id}`; línea sobre orden `DELIVERED` → `409 service_order_terminal`; borrar línea en `IN_REPAIR` → `204`; borrar en terminal → `409` |
| Transiciones (RF-06) | `test_transitions_api.py` | Camino completo `RECEIVED → DIAGNOSING → AWAITING_APPROVAL → IN_REPAIR → READY_FOR_PICKUP → DELIVERED` con `5+1` filas de historial en orden y `delivered_at` seteado; transición inválida (`RECEIVED → DELIVERED`) → `409 invalid_transition`, estado intacto y conteo de historial **sin cambios**; `READY_FOR_PICKUP` sin detalles → `409 details_required`; `GET /transitions` refleja `allowed`; `READY_FOR_PICKUP → IN_REPAIR` (retrabajo) → `200`; transición desde terminal → `409`; `comment` se persiste en el historial |
| Rechazo (RF-06 + RN-03) | `test_transitions_api.py` | `AWAITING_APPROVAL → REJECTED` con una línea "Diagnóstico" → `200`; `REJECTED → DELIVERED` fija `delivered_at`; el detalle de diagnóstico sigue siendo la única evidencia y no se altera |
| Reingreso (RF-09) | `test_warranty_api.py` | Entrega hace 89 días (`FrozenClock`) → `warranty/candidates` lo lista y `POST /service-orders` con `origin_service_id` → `201`; 90 y 91 días → candidato vacío y `409 warranty_expired`; origen de otro equipo → `409 warranty_equipment_mismatch`; origen no entregado → `409 origin_not_delivered`; segundo vínculo al mismo origen → `409 origin_already_linked`; el historial del equipo muestra ambos servicios |
| Abandono (RF-10) | `test_abandonment_api.py` | 29 días en `AWAITING_APPROVAL` → no aparece en candidatos y la transición da `409 threshold_not_reached`; 30 días + `confirm=true` → `200 ABANDONED`; 30 días sin `confirm` → `409 confirmation_required` y estado intacto; 180 días en `READY_FOR_PICKUP` → fuera de candidatos; 181 → dentro y transiciona; `ABANDONED` no aparece en el dashboard |
| Dashboard (RF-07) | `test_dashboard_api.py` | Lista solo no entregados con `customer_name`, `status_label` y `days_since_reception` correctos bajo `FrozenClock`; excluye `DELIVERED`/`ABANDONED`; orden por días descendente; `is_over_threshold` verdadero solo cuando corresponde |
| Historial (RF-08) | `test_equipments_api.py` | Equipo con 3 servicios (incluido un reingreso) → historial completo, ordenado, con estados y detalles; consulta por `internal_code` y por `serial_number` devuelve lo mismo |
| Repositorio | `test_service_order_repository.py` | Persistencia de la orden con sus detalles e historial; el historial no expone `update`/`delete`; `UNIQUE(internal_code)` se traduce en `IntegrityError` capturado → `409` |
| UI | `test_web_smoke.py` | `/` y `/reception` responden `200` y contienen textos en español ("Equipos en taller", "Falla reportada"); el formulario incluye los 5 campos obligatorios |

Toda integración verifica el **efecto observable completo**: código HTTP, cuerpo JSON y
estado persistido (releído en otra sesión), y que el rechazo **no** altera datos ni
contadores.

### 4.4 Organización de fixtures

**`tests/conftest.py` (raíz, compartido)**

| Fixture | Scope | Qué hace |
|---|---|---|
| `settings` | `session` | `Settings` de prueba con `DATABASE_URL="sqlite+pysqlite:///:memory:"` y umbrales de la spec (90/180/30) |
| `engine` | `function` | `create_engine` con `StaticPool` + `check_same_thread=False`; `metadata.create_all()` al entrar, `drop_all()` al salir. Una BD limpia por test: aislamiento total |
| `session` | `function` | `Session` ligada al engine; rollback y cierre en teardown |
| `clock` | `function` | `FrozenClock(datetime(2026, 10, 22, 15, 0, tzinfo=UTC))`, con `travel(days)` para mover el tiempo sin dormir |
| `seed` | `function` | Ejecuta `app.db.seed` (maestros base + `Diagnóstico`) sobre la sesión del test |
| `client` | `function` | `TestClient(create_app(...))` con `app.dependency_overrides` apuntando a la sesión y al reloj de prueba (sin tocar la BD real) |
| `frozen_now_lima` | `function` | Fecha de negocio derivada, para asserts de `days_in_status` |

**`tests/support/factories.py`** — constructores explícitos, sin aleatoriedad:

| Factory | Devuelve | Nota |
|---|---|---|
| `make_device_type`, `make_brand`, `make_component`, `make_operation` | maestro persistido | Reutilizan el `seed` cuando el nombre ya existe (evita duplicados accidentales) |
| `make_customer` | `Customer` | Nombre/teléfono únicos por contador interno del factory |
| `make_equipment` | `Equipment` | Llama al servicio real para obtener `internal_code` correlativo |
| `make_service_order` | `ServiceOrder` | Acepta `status` y `days_ago`; crea el historial coherente con el estado pedido (atajo válido, sin saltarse la matriz: recorre las transiciones) |
| `make_detail` | `ServiceDetail` | Operación "Diagnóstico" por defecto |

Principios de los fixtures:

1. **El atajo nunca miente.** Para ubicar una orden en `READY_FOR_PICKUP` se ejecutan las
   transiciones reales con el reloj congelado; no se escribe el estado a mano. Así el
   historial siempre es consistente y los tests de umbral son fiables.
2. **Sin `sleep` y sin `datetime.now()`** en tests: el tiempo se inyecta.
3. **Sin estado compartido entre tests:** BD en memoria nueva por test, factories sin
   globales mutables.
4. **`FrozenClock` implementa el puerto `Clock`** del dominio, no monkeypatchea módulos.
5. Los tests de API crean sus datos por HTTP cuando el caso lo permite (menos acoplamiento);
   las factories quedan para precondiciones largas.

### 4.5 Cobertura, CI y trazabilidad

**Comando de calidad (local y CI):**

| Paso | Comando | Puerta |
|---|---|---|
| Lint | `ruff check .` | 0 hallazgos |
| Formato | `ruff format --check .` | sin cambios pendientes |
| Unitarias | `pytest tests/unit -q` | 100 % en verde, < 2 s |
| Integración | `pytest tests/integration -q` | 100 % en verde |
| Cobertura | `pytest --cov=app.domain --cov=app.services --cov-branch --cov-report=term-missing --cov-fail-under=80` | ≥ 80 % (DoD) |

`pyproject.toml` fija `addopts` con `--cov-fail-under=80`, `-ra` y
`filterwarnings = ["error"]` (un `DeprecationWarning` de SQLAlchemy rompe el build: obliga
a mantener el ORM al día). El workflow `.github/workflows/ci.yml` corre los cinco pasos en
cada `push` y `pull_request` sobre Python 3.14 (NFR-06).

**Ruta a ≥ 80 %:** el dominio concentra la lógica y se cubre con unitarias de tabla
(parametrizadas por frontera), lo que da cobertura alta sin mocks. Los servicios se cubren
por la vía de integración —cada endpoint ejercita su servicio— más dos unitarias con dobles
para las ramas que la API no alcanza (baja de maestro en uso, `equipment_source_invalid`).
La UI se cubre con humo. Se excluye del cómputo `app/db/models` (declarativo) y
`app/main.py` (composición).

**Matriz de trazabilidad (Constitución §1.7)** — se mantiene al día en cada tarea:

| Dolor | Historia | Regla | Requisito | Pruebas |
|---|---|---|---|---|
| D1 | HU-07 Dashboard | RN-07, RN-10 | RF-07, RF-10 | `test_dashboard_api.py`, `test_abandonment_api.py`, `test_rules_abandonment.py` |
| D2 | HU-08 Historial | RN-02, RN-05 | RF-03, RF-08 | `test_equipments_api.py`, `test_transitions_api.py`, `test_state_machine.py` |
| — | HU-01 Maestros | RN-09 | RF-01 | `test_catalogs_api.py`, `test_catalog_rules.py` |
| — | HU-02 Clientes | — | RF-02 | `test_customers_api.py` |
| — | HU-03 Equipos | RN-01, RN-02 | RF-03 | `test_equipments_api.py`, `test_codes.py` |
| — | HU-04 Recepción | RN-06, RN-08 | RF-04 | `test_reception_api.py`, `test_rules_immutability.py` |
| — | HU-05 Operaciones | RN-03 | RF-05 | `test_details_api.py`, `test_rules_details.py` |
| D1 | HU-06 Estados | RN-05 | RF-06 | `test_transitions_api.py`, `test_state_machine.py` |
| D2 | HU-09 Garantía | RN-04 | RF-09 | `test_warranty_api.py`, `test_rules_warranty.py` |

### 4.6 Orden de implementación (TDD)

| Fase | Entregable | Primer test (RED) |
|---|---|---|
| 1 | `domain/enums.py` + `state_machine.py` | matriz completa: 15 válidas / inválidas / terminales |
| 2 | `domain/rules.py` (RN-03, RN-04, RN-07, RN-10) + `codes.py` | fronteras 89/90/91, 29/30/31, 179/180/181 |
| 3 | `db/models` + repositorios + `seed` | `UNIQUE(internal_code)`, ausencia de `customer_id` en `equipments` |
| 4 | `services` de catálogo, cliente y equipo | duplicados y correlativo vía servicio |
| 5 | Recepción + detalles + transiciones (API) | RF-04, RF-05, RF-06 completos |
| 6 | Dashboard, historial, garantía y abandono | RF-07, RF-08, RF-09, RF-10 |
| 7 | UI Jinja2 + `docs`/Swagger + CI | humo de vistas y `/openapi.json` con los RF |

Cada fase cierra con: tests en verde, cobertura ≥ 80 %, `ruff` limpio y el requisito
enlazado en la matriz de trazabilidad.
