# Desglose de Tareas (Tasks) — Sistema de Trazabilidad de Soporte Técnico (ReparaTrack)

**Versión:** 1.0 · **Fecha:** 22 de octubre de 2026
**Deriva de:** `01-spec.md` (v1.0) y `02-plan.md` (v1.0), sección 4.6 "Orden de implementación (TDD)".
**Alcance:** 37 tareas verticales en 7 fases y 2 iteraciones.

> Este documento no contiene código de producción. Cada fila describe **el test que falla
> primero** (RED), **la implementación mínima** que lo hace pasar (GREEN) y **la evidencia
> de terminado** (DoD). Ante cualquier contradicción, mandan la Constitución, la spec y el plan.

---

## 1. Regla de oro del desglose

> **Cada tarea es una unidad vertical: test + código + integración, en el mismo commit,
> con un solo objetivo y verificable por sí misma.**

Consecuencias operativas de la regla:

1. **Vertical, no por capas.** Ninguna tarea entrega "solo los modelos" o "solo el router".
   Cada tarea atraviesa lo mínimo de dominio → servicio → persistencia → API o UI para que
   un caso de uso quede observable de punta a punta.
2. **Un objetivo por tarea.** Si la descripción necesita la conjunción "y" para dos
   comportamientos independientes, son dos tareas. Las excepciones se marcan explícitamente.
3. **RED primero y concreto.** El test se escribe antes del código, falla por la razón
   correcta (no por `ImportError` de un módulo vacío ni por un `assert` trivial) y nombra el
   caso, la entrada y la aserción exacta.
4. **GREEN mínimo.** Se implementa lo estrictamente necesario para ese test; nada de
   "aprovecho y agrego" comportamiento no pedido.
5. **Verificable por sí misma.** La tarea se puede cerrar con un comando focalizado
   (`pytest tests/...::test_x -q`) sin depender de tareas futuras. Las dependencias hacia
   adelante se declaran como riesgo, nunca como "terminado a medias".
6. **PRESERVE obligatorio.** Si la tarea toca código existente (opciones, validadores,
   helpers compartidos), agrega un test que fija el comportamiento previo antes de tocarlo.
7. **Trazabilidad viva.** Al cerrar la tarea se actualiza la matriz del plan §4.5 con el
   requisito y el archivo de prueba. Una tarea sin fila en la matriz está incompleta.

### 1.1 Definición de terminado transversal (aplica a todas las tareas)

| Puerta | Criterio |
|---|---|
| Tests | Los tests de la tarea en verde y los previos sin regresión |
| Cobertura | `--cov-branch` ≥ 80 % en `app/domain` y `app/services` al cierre de fase |
| Lint | `ruff check .` y `ruff format --check .` sin hallazgos |
| Pureza del dominio | `app/domain` sin I/O, sin `datetime.now()`, sin importar `app.*` salvo `app.domain.*` |
| Tiempo | Fechas siempre explícitas o inyectadas por el puerto `Clock`; cero `sleep` en tests |
| Contraseñas | Ninguna columna, esquema ni respuesta expone el valor de una contraseña (RN-06) |
| Datos | Los casos rechazados no dejan filas ni consumen contadores |
| Documentación | Endpoint nuevo documentado en OpenAPI y matriz de trazabilidad actualizada |

### 1.2 Convención de tamaños

| Tamaño | Esfuerzo relativo | Señal |
|---|---|---|
| **S** | ≤ 4 h | Una función pura, una tabla de catálogo, un endpoint de lectura simple |
| **M** | 4–8 h | Un caso de uso completo con su test de integración y su mapeo de errores |
| **L** | 1–2 días | Un flujo que combina varias reglas y transacciones (recepción, transición) |

Los tamaños son **relativos entre sí**, no compromisos de calendario.

---

## 2. Mapa de fases e iteraciones

| # | Fase | Entregable del plan §4.6 | RF / HU | Iteración |
|---|---|---|---|---|
| 1 | Dominio: estados y matriz | `domain/enums.py` + `state_machine.py` | RF-06 / HU-06 | 1 |
| 2 | Dominio: reglas y códigos | `domain/rules.py` + `codes.py` | RN-02, RN-03, RN-04, RN-07, RN-10 | 1 |
| 3 | Persistencia | `db/models` + repositorios + `seed` | soporte de RF-01…RF-10 | 1 |
| 4 | Maestros, clientes y equipos | servicios de catálogo, cliente y equipo + API | RF-01, RF-02, RF-03 / HU-01…HU-03 | 1 |
| 5 | Recepción, detalle y transiciones | API de servicios, detalles y estados | RF-04, RF-05, RF-06 / HU-04…HU-06 | 1 |
| 6 | Dashboard e historial | dashboard, historial por equipo y por cliente | RF-07, RF-08 / HU-07, HU-08 | 1 — **cierra el MVP** |
| 7 | Garantía, abandono y cierre | garantía, abandono, UI de garantía, docs y CI | RF-09, RF-10 / HU-09, HU-10 + NFR-06 | 2 |

**Iteración 1 (MVP):** T-01 … T-31 → RF-01 a RF-08 completos y usables (maestros, clientes,
equipos, recepción, detalle, estados con historial, dashboard e historial).
**Iteración 2:** T-32 … T-37 → RF-09 (garantía), RF-10 (abandono), su UI, documentación y CI.

### 2.1 Índice de tareas

| ID | Fase | Iter. | RF | Tamaño |
|---|---|---|---|---|
| T-01 | 1 | 1 | RF-06 | S |
| T-02 | 1 | 1 | RF-06 | S |
| T-03 | 1 | 1 | RF-06 | M |
| T-04 | 2 | 1 | RN-04/07/10 | S |
| T-05 | 2 | 1 | RF-05 / RN-03 | S |
| T-06 | 2 | 1 | RF-09 / RN-04 | S |
| T-07 | 2 | 1 | RF-10 / RN-10 | S |
| T-08 | 2 | 1 | RF-10 / RN-07 | S |
| T-09 | 2 | 1 | RF-03 / RN-02 | S |
| T-10 | 3 | 1 | NFR-05 | S |
| T-11 | 3 | 1 | RF-01 / RN-09 | M |
| T-12 | 3 | 1 | RF-02, RF-03 | M |
| T-13 | 3 | 1 | RF-04, RF-06 | M |
| T-14 | 3 | 1 | RF-01, RF-02 | M |
| T-15 | 3 | 1 | RF-03 / RN-02 | M |
| T-16 | 4 | 1 | RF-01 / RN-09 | M |
| T-17 | 4 | 1 | RF-01 | M |
| T-18 | 4 | 1 | RF-02 | M |
| T-19 | 4 | 1 | RF-03 / RN-02 | M |
| T-20 | 4 | 1 | RF-03 | S |
| T-21 | 5 | 1 | RF-04 / RN-06,08 | L |
| T-22 | 5 | 1 | RF-06 / RN-05 | L |
| T-23 | 5 | 1 | RF-06 / RN-03,07,10 | M |
| T-24 | 5 | 1 | RF-05 / RN-03 | M |
| T-25 | 5 | 1 | RF-04 / RN-08 | M |
| T-26 | 5 | 1 | RF-06 | M |
| T-27 | 5 | 1 | RF-04, RF-06 | M |
| T-28 | 6 | 1 | RF-07 / RN-07,10 | M |
| T-29 | 6 | 1 | RF-07 | S |
| T-30 | 6 | 1 | RF-08 | M |
| T-31 | 6 | 1 | RF-08 | S |
| T-32 | 7 | 2 | RF-09 / RN-04 | L |
| T-33 | 7 | 2 | RF-09 | S |
| T-34 | 7 | 2 | RF-10 / RN-07,10 | M |
| T-35 | 7 | 2 | RF-10 / RN-07,10 | M |
| T-36 | 7 | 2 | NFR-06, NFR-05 | S |
| T-37 | 7 | 2 | NFR-06 | S |

---

## 3. Fase 1 — Dominio: estados y matriz de transiciones

**Objetivo:** fijar el vocabulario de los 10 estados y la matriz cerrada de RN-05 antes de
cualquier persistencia. **RF:** RF-06 (base). **Depende de:** nada.
**Cierre de fase:** 15 aristas válidas y 85 inválidas parametrizadas en verde, sin BD.

| ID | RF / HU | Descripción | RED (test que falla primero) | GREEN (implementación mínima) | DoD (criterio de terminado) |
|---|---|---|---|---|---|
| **T-01** | RF-06 / HU-06 | `domain/enums.py`: `ServiceStatus` con los **10 estados** de la spec y su etiqueta en español, más la marca de estado terminal. | `test_state_labels.py`: el enum tiene exactamente 10 miembros; cada uno tiene etiqueta ES no vacía y única; no hay etiquetas duplicadas; `DELIVERED` y `ABANDONED` son los únicos terminales; `parse("in_repair")` devuelve el miembro y `parse("en_reparacion")` lanza `UnknownStatusError` con `code="unknown_status"`. | Enum de texto con los 10 valores de la spec, diccionario de etiquetas ES ("Recibido", "En diagnóstico", "Esperando aprobación", "Esperando repuesto", "En reparación", "No reparable", "Rechazado", "Listo para entrega", "Entregado", "Abandonado") y `parse` que valida contra el enum. | 10/10 estados con etiqueta; ningún otro módulo escribe strings de estado a mano; `ruff` limpio. |
| **T-02** | RF-06 / HU-06 | `domain/errors.py`: `DomainError` base con `code` estable y `details` serializable, más las subclases de transición y de estado desconocido. | En `test_state_machine.py`: cada subclase expone el `code` acordado (`invalid_transition`, `details_required`, `threshold_not_reached`, `confirmation_required`, `unknown_status`) y `details` se serializa a JSON; `InvalidTransitionError` incluye `from_status`, `to_status` y `allowed`, y su mensaje nombra origen y destino. | Jerarquía de excepciones con `code` a nivel de clase y `details` armados en el constructor; `to_envelope()` que produce la forma `error.code/message/details`. | Los tests asertan tipo de error **y** su `code`, nunca el texto completo; el dominio no conoce códigos HTTP. |
| **T-03** | RF-06 / HU-06 | `domain/state_machine.py`: matriz cerrada de RN-05 con las **15 aristas válidas**, incluida `READY_FOR_PICKUP → IN_REPAIR` (retrabajo) y los dos terminales sin salida. | `test_state_machine.py`: las 15 aristas válidas parametrizadas devuelven `True`; las 85 combinaciones restantes de 10×10 lanzan `InvalidTransitionError`; `allowed_targets` coincide con la matriz para los 10 estados; `DELIVERED` y `ABANDONED` devuelven conjunto vacío; `READY_FOR_PICKUP → IN_REPAIR` está permitido; `RECEIVED → DELIVERED` no. | Diccionario de origen a conjunto de destinos, con `can_transition`, `allowed_targets` y `assert_transition`; sin ramas especiales por estado. | 15/15 válidas y 85/85 inválidas en verde; la matriz se lee como dato, no como cadena de `if`; cubre el 100 % de las ramas de `state_machine`. |

---

## 4. Fase 2 — Dominio: reglas temporales y códigos

**Objetivo:** aislar en funciones puras (con `as_of` explícito) las cuatro reglas con umbral,
la inmutabilidad y el formato del código correlativo. **RF:** soporte de RF-03, RF-05,
RF-09, RF-10. **Depende de:** Fase 1.
**Cierre de fase:** fronteras 89/90/91, 29/30/31 y 179/180/181 fijadas; cero `datetime.now()`.

| ID | RF / HU | Descripción | RED (test que falla primero) | GREEN (implementación mínima) | DoD (criterio de terminado) |
|---|---|---|---|---|---|
| **T-04** | RN-04, RN-07, RN-10 | `domain/rules.py`: base temporal común. `business_date(dt)` y `days_between(start, as_of)` sobre **fecha calendario de negocio en `America/Lima`**, aunque se persista UTC. | `test_rules_abandonment.py`: un instante UTC del día 22 a las 21:00 de Lima contra `as_of` del 22 a las 23:00 → 0 días; contra el 23 a las 00:30 → 1 día; un rango de 30 días calendario devuelve exactamente 30 (sin redondeos por horas). | Conversión a zona `America/Lima`, extracción de fecha local y diferencia en días calendario; funciones puras que reciben `as_of`. | Ninguna función usa `datetime.now()`; todos los umbrales de la fase consumen esta base; test de frontera horaria en verde. |
| **T-05** | RF-05 / RN-03 | `domain/rules.py`: RN-03 — `READY_FOR_PICKUP` exige **≥ 1 línea de detalle**. No se aplica en la creación ni en otros destinos. | `test_rules_details.py`: 0 detalles hacia `READY_FOR_PICKUP` lanza `DetailsRequiredError` con `code="details_required"` y `details_count=0`; 1 detalle permite; 5 permiten; los destinos `IN_REPAIR` y `AWAITING_PART` nunca se bloquean; el chequeo no inspecciona el texto de la descripción. | `ensure_details_for_pickup(details_count, target)`: actúa solo si el destino es `READY_FOR_PICKUP`. | Regla aislada de la BD y de la API; "Diagnóstico" no es caso especial en el código (T-24 lo prueba con la operación sembrada). |
| **T-06** | RF-09 / RN-04 | `domain/rules.py`: elegibilidad de garantía con umbral de **90 días** desde la entrega. El sistema alerta; no compara texto de fallas. | `test_rules_warranty.py`: 0 y 89 días → elegible con `warranty_days_left` 90 y 1; **90 y 91 → no elegible**; origen en estado distinto de `DELIVERED` → no elegible con `reason`; un servicio sin origen no consulta garantía; todos los casos con `as_of` explícito. | `warranty_eligibility(delivered_at, status, as_of)` que devuelve elegibilidad, días transcurridos, días restantes y motivo. | Frontera 89/90/91 fijada por parametrización; la función no muta la entrada ni consulta repositorios. |
| **T-07** | RF-10 / RN-10 | `domain/rules.py`: RN-10 — desde `AWAITING_APPROVAL`, **≥ 30 días** sin respuesta habilita `ABANDONED`, solo con confirmación. | `test_rules_abandonment.py`: 29 días → no elegible; **30 → elegible**; 31 → elegible; `confirm=False` lanza `ConfirmationRequiredError`; desde otro estado la regla no aplica; `rule="RN-10"`. | Extiende la elegibilidad de abandono con la rama RN-10 (`días >= 30`) y el gate de confirmación. | Asimetría inclusiva de RN-10 fijada con tests; `threshold_not_reached` acarrea `days_in_status` y `required_days`. |
| **T-08** | RF-10 / RN-07 | `domain/rules.py`: RN-07 — desde `READY_FOR_PICKUP`, **más de 180 días** habilita `ABANDONED`, solo con confirmación. | `test_rules_abandonment.py`: 179 y **180 → no elegible**; **181 → elegible**; `confirm=False` lanza `ConfirmationRequiredError`; `rule="RN-07"`; el día 180 exacto no habilita porque la spec dice "supera 180 días". | Extiende la misma función con la rama RN-07 (`días > 180`), sin tocar la rama RN-10. | Ambas asimetrías (`>= 30` y `> 180`) conviven y están fijadas; ninguna se normaliza "por simetría". |
| **T-09** | RF-03 / RN-02 | `domain/codes.py`: formato del código interno correlativo `EQ-` + seis dígitos, independiente del `id` de la fila. | `test_codes.py`: `1 → EQ-000001`, `42 → EQ-000042`, `999999 → EQ-999999`; ancho fijo de 6 con ceros a la izquierda; `0` y negativos lanzan `ValueError`; `1000000` se rechaza por desbordamiento; el resultado no depende del `id` de la entidad. | `format_internal_code(sequence)` y su inverso `parse_internal_code(code)` para búsquedas. | Módulo puro, sin SQLAlchemy; el contador real se conecta en T-15. |

---

## 5. Fase 3 — Persistencia: modelos, semilla y repositorios

**Objetivo:** materializar el modelo de datos del plan §2 y las invariantes estructurales
(equipo sin dueño, código único, bitácora append-only). **RF:** soporte.
**Depende de:** Fases 1–2. **Cierre de fase:** `create_all` reproduce el esquema y las
invariantes se prueban insertando datos inválidos, no con comentarios.

| ID | RF / HU | Descripción | RED (test que falla primero) | GREEN (implementación mínima) | DoD (criterio de terminado) |
|---|---|---|---|---|---|
| **T-10** | soporte (NFR-05) | Primer corte vertical de infraestructura: `config.Settings` (umbrales 90/180/30, `DATABASE_URL`), motor y sesión SQLite, `create_app()` y `GET /api/v1/health`. | `test_health_api.py`: `GET /api/v1/health` → `200` con estado `ok` y base `ok` sobre SQLite en memoria; `Settings` expone `warranty_days=90`, `abandonment_days=180`, `approval_days=30` y acepta override por entorno; la app crea el esquema al arrancar. | `Settings` tipado, engine + fábrica de sesiones, `create_app()` que registra el router de salud y ejecuta `create_all()`. | La app se instancia en tests sin tocar la BD real; `dependency_overrides` de sesión y reloj quedan disponibles para el resto de fases. |
| **T-11** | RF-01 / RN-09 | Modelos de los cuatro maestros (`device_types`, `brands`, `components`, `operation_types`) con `name` único, `is_active` y `created_at`; `seed.py` con los valores base y **"Diagnóstico"** en operaciones. | `test_catalog_repository.py`: tras la semilla, los cuatro catálogos tienen sus valores base; `operation_types` contiene **"Diagnóstico" una sola vez**; `is_active` nace en verdadero; ejecutar la semilla dos veces no duplica; un `name` repetido produce `IntegrityError`; un nombre vacío o solo espacios se rechaza. | Cuatro modelos con `UNIQUE(name)` y validación de no vacío; semilla idempotente que incluye "Diagnóstico" como dato. | "Diagnóstico" existe por semilla y no por rama de código; la semilla es reutilizable por las fixtures de T-14 en adelante. |
| **T-12** | RF-02, RF-03 | Modelos `customers`, `equipments`, `code_counters` con FK `RESTRICT` a maestros, `serial_number` opcional y `internal_code` único. **Sin `equipments.customer_id`.** | `test_equipments_api.py` (estructural) + `test_service_order_repository.py`: `inspect(engine)` demuestra que `equipments` **no** tiene columna `customer_id` ni existe tabla de unión cliente–equipo; `serial_number` acepta nulo; repetir `internal_code` produce `IntegrityError`; borrar un `device_type` referenciado falla; `code_counters.last_value` no admite negativos. | Modelos declarativos con columnas, FKs e índices del plan §2.4–§2.5; la propiedad del equipo queda solo en `service_orders`. | La invariante estructural se verifica automáticamente sobre los metadatos, no con una nota; el dueño vigente se deriva del último servicio. |
| **T-13** | RF-04, RF-06 | Modelos `service_orders`, `service_details` y `state_history` con las restricciones de coherencia del plan §2.6–§2.8. | `test_service_order_repository.py`: un `status` fuera de los **10 estados** → `IntegrityError`; `DELIVERED` con `delivered_at` nulo → `IntegrityError`; `delivered_at` con estado distinto de `DELIVERED` → `IntegrityError`; `origin_service_id` igual al propio `id` → `IntegrityError`; dos servicios con el mismo `origin_service_id` → `IntegrityError`; el repositorio de historial no expone métodos de actualización ni borrado. | Modelos con `CHECK` de estado, `CHECK` de coherencia estado/fecha, `CHECK` de auto-referencia y `UNIQUE(origin_service_id)`; `native_enum=False` con `create_constraint` activo. | Los `CHECK` se emiten de verdad en SQLite (probado insertando datos inválidos, no leyendo el DDL); la bitácora nace append-only. |
| **T-14** | RF-01, RF-02 | Implementaciones de `CatalogRepository` (genérica para los cuatro maestros) y `CustomerRepository`, satisfaciendo los puertos de `services/ports.py`. | `test_catalog_repository.py`: alta y relectura en otra sesión; `list_active` excluye inactivos; `find_by_normalized_name(" ram ")` encuentra "RAM"; `count_usages` detecta un tipo de dispositivo referenciado por un equipo y devuelve 0 para un valor libre; búsqueda de clientes por nombre y por teléfono. | Repositorios con `select()` y normalización `trim` + `casefold`; `commit` solo en la capa `db`. | Los puertos quedan satisfechos sin filtrar SQLAlchemy hacia `services`; normalización centralizada en un solo lugar. |
| **T-15** | RF-03 / RN-02 | `EquipmentRepository`: asignación **atómica** del código correlativo desde `code_counters` y búsquedas por código y por serial. | `test_equipments_api.py` + `test_service_order_repository.py`: la primera asignación entrega `EQ-000001` y la segunda `EQ-000002` sin huecos; un rollback de la transacción **no** avanza el contador; un `INSERT` con código repetido se traduce en conflicto de negocio, no en error 500; la búsqueda por serial repetido devuelve el equipo correcto. | Incremento del contador dentro de la misma transacción del alta, más el formateo de `codes.py`; búsquedas por `internal_code` y `serial_number`. | No se usa `MAX(id)+1`; el contador es atómico y sobrevive a reintentos sin reutilizar códigos. |

---

## 6. Fase 4 — Maestros, clientes y equipos (RF-01, RF-02, RF-03)

**Objetivo:** primer bloque funcional completo y usable: catálogos administrables, clientes y
equipos con código correlativo. **RF:** RF-01, RF-02, RF-03.
**Depende de:** Fase 3. **Cierre de fase:** RF-01, RF-02 y RF-03 (excepto el historial
completo, que cierra en T-30) verificados por API y por vista.

| ID | RF / HU | Descripción | RED (test que falla primero) | GREEN (implementación mínima) | DoD (criterio de terminado) |
|---|---|---|---|---|---|
| **T-16** | RF-01 / HU-01 | `CatalogService`: alta y renombrado con **duplicado normalizado**, baja lógica y negativa a borrar valores **en uso** (RN-09). | `test_catalog_rules.py`: crear "RAM" y luego " ram " produce `CatalogDuplicateError` con `code="catalog_duplicate"`; renombrar a un nombre existente da el mismo error; borrar un valor en uso lanza `CatalogValueInUseError` con `code="catalog_value_in_use"` y `hint`; dos bajas lógicas seguidas son idempotentes; un valor inactivo con el mismo nombre sigue bloqueando el alta. | Servicio sobre el repositorio: normaliza antes de comparar, incluye inactivos en la comparación y delega la baja lógica. | Ambos criterios de RF-01 cubiertos por test; el servicio no importa SQLAlchemy ni FastAPI. |
| **T-17** | RF-01 | API simétrica de los cuatro maestros y vista de administración: listar, obtener, crear, renombrar, desactivar, reactivar y borrar. | `test_catalogs_api.py`: `POST` → `201`; duplicado con espacios o mayúsculas → `409 catalog_duplicate`; `DELETE` sin uso → `204` y el valor desaparece del listado; `DELETE` en uso → `409 catalog_value_in_use` y el valor sigue existiendo; `deactivate` → `200` y deja de aparecer con `active=true`; `GET /catalogs` (UI) → `200` con los cuatro maestros. | Router parametrizado por recurso, esquemas de lectura con `in_use`, mapeo `DomainError → HTTP` y plantilla de administración. | Los cuatro recursos se prueban por parametrización (simetría real); los mensajes visibles van en español neutro. |
| **T-18** | RF-02 / HU-02 | `CustomerService` y API: alta con contacto, búsqueda por nombre/teléfono/documento y actualización de contacto. | `test_customers_api.py`: alta completa → `201`; sin `phone` → `422` con `details.field="phone"`; documento duplicado → `409 document_duplicate`; correo con formato inválido → `422`; `GET /customers?q=` encuentra por nombre y por teléfono. | Servicio con validación de contacto mínimo y correo opcional; router con paginación `limit/offset` y total. | Los casos rechazados no dejan clientes persistidos; la búsqueda no depende de coincidencia exacta de mayúsculas. |
| **T-19** | RF-03 / HU-03 | `EquipmentService.create` y `POST /equipments`: alta con **código interno correlativo** y serial opcional. | `test_equipments_api.py`: primer alta → `201` con `EQ-000001`; segunda → `EQ-000002` sin huecos; `serial_number` omitido → `201` con `null`; `device_type_id` o `brand_id` inexistente → `422`; un alta fallida no consume correlativo. | Servicio que valida maestros activos, solicita el código al repositorio y persiste en una transacción; respuesta con tipo y marca anidados. | RN-02 verificado por API; `current_owner` devuelve `null` cuando el equipo no tiene servicios (contrato explícito, no error). |
| **T-20** | RF-03 / HU-03 | `EquipmentService.lookup` y `GET /equipments/lookup`: identificar un equipo por **código o serial conocido** y anticipar su historial. | `test_equipments_api.py`: `?internal_code=EQ-000001` y `?serial_number=SN-1` devuelven el mismo equipo con `previous_services_count`; sin parámetros → `422`; código inexistente → `404`; con ambos parámetros, el código tiene precedencia (decisión D-06) y el test lo fija. | Servicio de búsqueda con precedencia declarada y conteo de servicios por equipo. | RF-03 criterio 2 queda **parcial y declarado**: devuelve el conteo; el historial completo se cierra en T-30 (riesgo R-01). |

---

## 7. Fase 5 — Recepción, detalle y transiciones (RF-04, RF-05, RF-06)

**Objetivo:** el corazón del sistema. Recepción con historial inicial, líneas de detalle y
máquina de estados con guardas. **RF:** RF-04, RF-05, RF-06.
**Depende de:** Fases 2–4. **Cierre de fase:** camino completo de 6 estados, rechazo sin
efectos, RN-03 y RN-08 activas, UI de recepción y ficha funcionando.

| ID | RF / HU | Descripción | RED (test que falla primero) | GREEN (implementación mínima) | DoD (criterio de terminado) |
|---|---|---|---|---|---|
| **T-21** | RF-04 / HU-04 | `ServiceOrderService.create` y `POST /service-orders`: recepción con 5 campos obligatorios, equipo existente **o** nuevo (exactamente uno) y **primera fila de historial `RECEIVED`** en la misma transacción. | `test_reception_api.py`: recepción completa → `201` con `status=RECEIVED` y `received_at` con zona; exactamente **1** fila `RECEIVED` en el historial; sin `reported_failure` → `422` con `details.field="reported_failure"` y cero servicios y cero equipos nuevos; `equipment_id` + `new_equipment` a la vez → `422 equipment_source_invalid`; ninguno de los dos → el mismo error; `new_equipment` crea el equipo y la respuesta trae su `internal_code`; `password_requested` por defecto `false`; la respuesta solo expone el booleano, nunca un valor de contraseña. | Servicio que resuelve el equipo (existente o creado en la misma transacción), toma la fecha del puerto `Clock`, persiste la orden y su fila inicial de historial. | RN-01, RN-06 y RN-08 quedan registrados desde la recepción; las validaciones ocurren antes de cualquier escritura. |
| **T-22** | RF-06 / HU-06 | `ServiceOrderService.transition` y `POST /service-orders/{id}/transitions`: matriz cerrada, **una fila de historial por transición** y fijación de `delivered_at`. | `test_transitions_api.py`: el camino `RECEIVED → DIAGNOSING → AWAITING_APPROVAL → IN_REPAIR → READY_FOR_PICKUP → DELIVERED` produce **6 filas** de historial en orden y `delivered_at` seteado; `RECEIVED → DELIVERED` → `409 invalid_transition`, estado intacto y conteo de historial **sin cambios**; transición desde `DELIVERED` o `ABANDONED` → `409`; el `comment` se persiste en la fila. | Servicio que valida con `state_machine`, actualiza estado, agrega la fila de historial y fija `delivered_at` en los destinos que corresponden, todo en una transacción. | Rechazo sin efectos verificable comparando estado y conteo de historial antes y después; la bitácora nunca queda vacía. |
| **T-23** | RF-06 / RN-03, RN-07, RN-10 | Guardas de la transición: detalle mínimo para `READY_FOR_PICKUP` y umbral más confirmación para `ABANDONED`, con errores de contexto explícito. | `test_transitions_api.py`: `READY_FOR_PICKUP` con 0 detalles → `409 details_required` con `details_count=0`; `AWAITING_APPROVAL → ABANDONED` en día 29 → `409 threshold_not_reached` con `rule="RN-10"` y `required_days=30`; día 30 sin `confirm` → `409 confirmation_required`; `READY_FOR_PICKUP` en día 180 → `409 threshold_not_reached` con `rule="RN-07"`; en los cuatro casos estado e historial intactos. | `transition` evalúa las guardas del dominio **antes** de escribir y traduce cada rechazo a su error con `details`. | Los cuatro errores del contrato §3.6 existen con su código y contexto; ninguna guarda se ejecuta "después" de persistir. |
| **T-24** | RF-05 / HU-05 | `ServiceDetailService` y endpoints de detalle: alta con componente opcional, baja de corrección y bloqueo en órdenes terminales. Incluye el **flujo de rechazo con "Diagnóstico"**. | `test_details_api.py`: alta con componente → `201`; sin componente (formateo) → `201`; `details_count` sube en `GET /service-orders/{id}`; línea sobre orden `DELIVERED` → `409 service_order_terminal`; borrar una línea en `IN_REPAIR` → `204`; borrar en terminal → `409`; `AWAITING_APPROVAL → REJECTED` con una única línea de operación "Diagnóstico" → `200`; `REJECTED → DELIVERED` fija `delivered_at` y la línea no se altera. | Servicio de detalles con guarda de estado terminal y conteo expuesto en la lectura de la orden; sin `UNIQUE` sobre operación/componente. | RN-03 se satisface con una línea real de "Diagnóstico", sin campos falseados ni excepciones en el código. |
| **T-25** | RF-04 / RN-08 | Inmutabilidad de `physical_condition` con **tres barreras**: sin endpoint que la reciba, esquema de actualización cerrado y listener de persistencia. | `test_rules_immutability.py` + `test_reception_api.py`: `assert_condition_immutable` permite el mismo valor, lanza `ImmutableFieldError` con valor distinto o con `None` sobre un valor previo, y no muta la entrada; `PATCH /service-orders/{id}` con `physical_condition` → `422 immutable_field`; forzar el cambio por ORM dispara el listener y no llega a la BD. | Función pura de comparación, esquema de actualización con campos extra prohibidos y listener previo al flush. | Las tres barreras se prueban por separado; ninguna ruta, presente o futura, permite editar la condición física. |
| **T-26** | RF-06 / HU-06 | Endpoints de lectura: ficha con días y transiciones permitidas, bandeja filtrable y listado de destinos con guardas evaluadas. | `test_transitions_api.py` + `test_reception_api.py`: `GET /service-orders/{id}` devuelve `status_label`, `days_in_status`, `days_since_reception`, `details_count` y `allowed_transitions`; `GET /service-orders/{id}/transitions` marca `blocked_reason` cuando falta detalle o umbral; `GET /service-orders?status=` filtra y pagina; id inexistente → `404`. | Router de lectura y esquema de respuesta calculado con el reloj inyectado; destinos enriquecidos con el motivo de bloqueo. | La UI puede habilitar o deshabilitar botones sin duplicar reglas de negocio. |
| **T-27** | RF-04, RF-06 | UI de recepción y ficha de servicio: formulario de 5 campos, historial visible y botones solo para transiciones permitidas. | `test_web_smoke.py`: `GET /reception` → `200` con las etiquetas de los cinco campos obligatorios; `POST /reception` válido → redirección a la ficha; la ficha muestra el estado en español, el historial y solo los destinos permitidos; una transición inválida muestra mensaje en español y no cambia el estado. | Rutas web, modelos de vista con etiquetas y días, y plantillas de recepción, ficha y parcial de estado. | La UI consume los servicios, no la API HTTP; funciona sin JavaScript (formularios HTML). |

---

## 8. Fase 6 — Dashboard e historial (RF-07, RF-08) — cierre de la Iteración 1

**Objetivo:** responder los dos dolores del negocio: "¿en qué estado está mi equipo?" y
"¿qué le hice antes a este equipo?". **RF:** RF-07, RF-08.
**Depende de:** Fase 5. **Cierre de fase:** MVP completo (RF-01…RF-08) sobre API y UI.

| ID | RF / HU | Descripción | RED (test que falla primero) | GREEN (implementación mínima) | DoD (criterio de terminado) |
|---|---|---|---|---|---|
| **T-28** | RF-07 / HU-07 | `DashboardService.workbench`, `GET /dashboard/workbench` y vista `/`: "equipos en taller" con cliente, estado y **días transcurridos**. | `test_dashboard_api.py`: con reloj congelado, lista solo servicios sin entregar con `customer_name`, `status_label` y `days_since_reception` correctos; excluye `DELIVERED` y `ABANDONED`; ordena por días descendente; `is_over_threshold` es verdadero solo cuando la regla aplica; `threshold_rule` informa `RN-07`, `RN-10` o nulo. | Servicio de consulta con una sola consulta con join (sin N+1), cálculo de días con el reloj inyectado y plantilla del dashboard. | RF-07 completo; la consulta no escala en número de sentencias con la cantidad de filas (verificado estructuralmente, sin tests de tiempo). |
| **T-29** | RF-07 | `DashboardService.summary` y `GET /dashboard/summary`: conteo por estado y alertas de umbral separadas por regla. | `test_dashboard_api.py`: `by_status` contiene las **10 claves** (con cero cuando no hay casos); `alerts` separa el grupo RN-07 del grupo RN-10; los conteos respetan las fronteras 30 y 181. | Dos agregaciones independientes sobre la misma fuente, sin lógica de umbral duplicada (reutiliza T-07/T-08). | Los dos grupos de abandono nunca se mezclan; el resumen no recalcula umbrales por su cuenta. |
| **T-30** | RF-08 / HU-08 | `EquipmentService.history`, `GET /equipments/{id}/history` y vista: historial técnico completo del equipo, incluido el reingreso vinculado. | `test_equipments_api.py`: equipo con 3 servicios (uno vinculado por garantía) devuelve los 3 ordenados, cada uno con su cliente, estado actual, historial de estados y detalles; `include=details,states` filtra secciones; consultar por `internal_code` y por `serial_number` devuelve lo mismo. | Servicio de historial que compone servicios, detalles e historial de estados; plantilla de historial de equipo. | Cierra R-01: el criterio 2 de RF-03 ("muestro su historial previo") queda completo; el historial sobrevive al cambio de dueño. |
| **T-31** | RF-08 | `CustomerService.history` y `GET /customers/{id}/history`: servicios del cliente con filtro por rango de recepción. | `test_customers_api.py`: cliente con 2 servicios devuelve ambos ordenados por fecha descendente; el filtro `from`/`to` recorta por `received_at`; cliente sin servicios → `[]` con `200`. | Consulta por cliente y rango de fechas, reutilizando el resumen de servicio. | Spec §4 ("historial por equipo y por cliente") cubierta de punta a punta. |

---

## 9. Fase 7 — Garantía, abandono y cierre de calidad (Iteración 2)

**Objetivo:** cerrar RF-09 y RF-10 y dejar el proyecto entregable: documentación, contrato
OpenAPI y automatización. **RF:** RF-09, RF-10, NFR-05, NFR-06.
**Depende de:** Fase 6. **Cierre de fase:** 37/37 tareas cerradas, CI verde en cada push.

| ID | RF / HU | Descripción | RED (test que falla primero) | GREEN (implementación mínima) | DoD (criterio de terminado) |
|---|---|---|---|---|---|
| **T-32** | RF-09 / HU-09 | `WarrantyService`, endpoints de candidatos y elegibilidad, y validación del vínculo en la recepción: **< 90 días** ofrece vincular; **≥ 90 días** obliga a servicio nuevo. | `test_warranty_api.py`: entrega hace 89 días → aparece en `candidates` con `warranty_days_left=1` y el alta con `origin_service_id` → `201`; 90 y 91 días → candidatos vacíos y `409 warranty_expired`; origen de otro equipo → `409 warranty_equipment_mismatch`; origen no `DELIVERED` → `409 origin_not_delivered`; segundo vínculo al mismo origen → `409 origin_already_linked`; el historial del equipo muestra ambos servicios. | Servicio de garantía con candidatos y elegibilidad; validación del vínculo dentro de la creación del servicio, en la misma transacción. | RN-04 se respeta: el sistema alerta y el técnico decide; no se compara ni se bloquea por el texto de la falla. |
| **T-33** | RF-09 | UI de garantía en la recepción: bloque de candidatos con días desde la entrega y elección explícita entre vincular o crear servicio nuevo. | `test_web_smoke.py`: con candidatos disponibles, la vista de recepción muestra el aviso en español con los días transcurridos y ambas opciones; sin candidatos, el bloque no se renderiza; elegir "servicio nuevo" envía la recepción sin `origin_service_id`. | Modelo de vista con candidatos y bloque condicional en la plantilla de recepción. | La decisión queda en el técnico, sin JavaScript obligatorio y sin vínculo automático. |
| **T-34** | RF-10 / HU-10 | `AbandonmentService`, `GET /abandonment/candidates` y filtro por regla: dos grupos **nunca mezclados**, RN-10 (≥ 30 días) y RN-07 (> 180 días). | `test_abandonment_api.py`: 29 días en `AWAITING_APPROVAL` → no aparece; 30 días → aparece con `rule="RN-10"`; 180 días en `READY_FOR_PICKUP` → no aparece; 181 días → aparece con `rule="RN-07"`; `?rule=RN-10` devuelve solo ese grupo; cada candidato trae cliente, código de equipo, días y umbral. | Servicio que reutiliza la elegibilidad de T-07/T-08 y agrupa por regla; endpoint con filtro opcional. | Ambas fronteras fijadas con reloj congelado; los grupos son excluyentes por construcción. |
| **T-35** | RF-10 / RN-07, RN-10 | Cierre del abandono de punta a punta: transición manual `ABANDONED` con confirmación y exclusión del dashboard. | `test_abandonment_api.py`: 30 días + `confirm=true` → `200 ABANDONED` y fila de historial; 30 días sin `confirm` → `409 confirmation_required` y estado intacto; 181 días + `confirm=true` desde `READY_FOR_PICKUP` → `200`; `ABANDONED` no aparece en el workbench ni admite transiciones posteriores. | Integración de la guarda ya existente (T-23) con la exclusión del dashboard; sin cambios en la matriz. | RN-07 y RN-10 cerrados de punta a punta; no existe job automático: la marca siempre es manual y confirmada. |
| **T-36** | NFR-05, NFR-06 | Cierre documental: metadatos OpenAPI con resumen en español por endpoint, README (arranque, comandos de calidad, respaldo de SQLite) y matriz de trazabilidad sin filas pendientes. | `test_web_smoke.py` (verificación estructural): `GET /openapi.json` incluye las rutas de RF-01 a RF-10 y el esquema de error uniforme. **Excepción de TDD:** la prosa del README no tiene RED de comportamiento; se verifica por revisión contra las secciones 3 y 4 del plan. | Anotaciones de OpenAPI en los routers, README y tabla de trazabilidad actualizada. | Todo RF tiene al menos un endpoint documentado y su fila en la matriz; el respaldo queda explicado en pasos reproducibles. |
| **T-37** | NFR-06 | Automatización de calidad: `pyproject.toml` con `addopts` (umbral de cobertura, `-ra`, warnings como error), `.pre-commit-config.yaml` y workflow de CI con los cinco pasos. | Ejecutar la secuencia de calidad sin configuración → `pytest` no aplica el umbral de 80 % ni `--cov-branch`, `ruff format --check .` reporta archivos sin formatear y no existe workflow. **Excepción de TDD:** es una tarea de configuración, se verifica ejecutando los comandos, no con un test de comportamiento. | `pyproject.toml` con las puertas del plan §4.5, pre-commit con lint y tests rápidos, y workflow que corre lint, formato, unitarias, integración y cobertura en cada push y pull request. | Los cinco comandos pasan en local y en CI; el build falla ante un `DeprecationWarning` de SQLAlchemy. |

---

## 10. Estimación de esfuerzo y cronograma

### 10.1 Esfuerzo por fase

| Fase | Iteración | Tareas | IDs | S | M | L | Esfuerzo relativo (S=0.5 · M=1 · L=2) | % |
|---|---|---|---|---|---|---|---|---|
| 1 — Dominio: estados y matriz | 1 | 3 | T-01…T-03 | 2 | 1 | 0 | 2.0 | 6 % |
| 2 — Dominio: reglas y códigos | 1 | 6 | T-04…T-09 | 6 | 0 | 0 | 3.0 | 9 % |
| 3 — Persistencia | 1 | 6 | T-10…T-15 | 1 | 5 | 0 | 5.5 | 17 % |
| 4 — Maestros, clientes y equipos | 1 | 5 | T-16…T-20 | 1 | 4 | 0 | 4.5 | 14 % |
| 5 — Recepción, detalle y transiciones | 1 | 7 | T-21…T-27 | 0 | 5 | 2 | 9.0 | 28 % |
| 6 — Dashboard e historial | 1 | 4 | T-28…T-31 | 2 | 2 | 0 | 3.0 | 9 % |
| 7 — Garantía, abandono y cierre | 2 | 6 | T-32…T-37 | 3 | 2 | 1 | 5.5 | 17 % |
| **Total** | — | **37** | — | **15** | **19** | **3** | **32.5** | **100 %** |

| Corte | Tareas | Esfuerzo | Participación |
|---|---|---|---|
| **Iteración 1 — MVP (RF-01…RF-08)** | 31 (T-01…T-31) | 27.0 | 83 % |
| **Iteración 2 — Garantía, abandono y CI** | 6 (T-32…T-37) | 5.5 | 17 % |

### 10.2 Lectura del cronograma

- **Ruta crítica:** T-13 → T-15 → T-21 → T-22/T-23 → T-28/T-30. Un desvío en la fase 3 o 5
  mueve todo el MVP; las fases 2 y 4 tienen holgura.
- **Dos escenarios de calendarización** (el esfuerzo es relativo, no una promesa):
  dedicación parcial de ~2.5 unidades por semana → ~13 semanas; dedicación intensiva de
  ~5 unidades por semana → ~6.5 semanas.
- **Punto de entrega parcial defendible:** al cerrar T-31 (27.0 unidades) el sistema ya
  cubre los dolores D1 y D2 con datos reales; la Iteración 2 agrega valor sin rehacer nada.
- **Fase 5 concentra el 28 % del esfuerzo.** Si hay que recortar, se recorta alcance de UI
  (T-27), nunca las guardas de T-23.

---

## 11. Matriz de trazabilidad RF → tareas → pruebas

| RF / HU | Tareas | Archivos de prueba | Regla |
|---|---|---|---|
| RF-01 / HU-01 Maestros | T-11, T-14, T-16, T-17 | `test_catalog_rules.py`, `test_catalog_repository.py`, `test_catalogs_api.py` | RN-09 |
| RF-02 / HU-02 Clientes | T-12, T-14, T-18, T-31 | `test_customers_api.py`, `test_catalog_repository.py` (casos de `CustomerRepository`) | — |
| RF-03 / HU-03 Equipos | T-09, T-12, T-15, T-19, T-20, T-30 | `test_codes.py`, `test_equipments_api.py` | RN-01, RN-02 |
| RF-04 / HU-04 Recepción | T-13, T-21, T-25, T-27 | `test_reception_api.py`, `test_rules_immutability.py`, `test_web_smoke.py` | RN-06, RN-08 |
| RF-05 / HU-05 Operaciones | T-05, T-24 | `test_rules_details.py`, `test_details_api.py` | RN-03 |
| RF-06 / HU-06 Estados | T-01, T-02, T-03, T-22, T-23, T-26, T-27 | `test_state_machine.py`, `test_state_labels.py`, `test_transitions_api.py` | RN-05 |
| RF-07 / HU-07 Dashboard | T-04, T-28, T-29 | `test_dashboard_api.py` | RN-07, RN-10 |
| RF-08 / HU-08 Historial | T-13, T-30, T-31 | `test_equipments_api.py`, `test_customers_api.py`, `test_service_order_repository.py` | RN-02, RN-05 |
| RF-09 / HU-09 Garantía | T-06, T-32, T-33 | `test_rules_warranty.py`, `test_warranty_api.py`, `test_web_smoke.py` | RN-04 |
| RF-10 / HU-10 Abandono | T-07, T-08, T-34, T-35 | `test_rules_abandonment.py`, `test_abandonment_api.py` | RN-07, RN-10 |
| NFR-05 / Respaldo | T-36 | verificación manual reproducible documentada en `README.md` §3 | — |
| NFR-06 / CI | T-36, T-37 | comandos de calidad del plan §4.5 | — |

---

## 12. Decisiones tomadas y riesgos abiertos

### 12.1 Decisiones

| ID | Decisión | Motivo |
|---|---|---|
| **D-01** | El orden de construcción sigue el plan §4.6 (dominio primero), no la secuencia funcional "maestros → clientes → recepción". | La máquina de estados y las reglas son dependencias de recepción y transiciones, y se prueban sin BD ni API. Construirlas al final obligaría a reescribir los servicios ya probados. |
| **D-02** | La UI de cada requisito se construye en la fase de ese requisito (T-17, T-27, T-28, T-30, T-33), no toda al final. | Una vista no se puede probar por humo antes de que exista el caso de uso que renderiza. La fase 7 conserva solo la UI de garantía y el cierre transversal. |
| **D-03** | RN-10 se codifica como `>= 30` y RN-07 como `> 180`, sin "normalizar" la asimetría. | La spec dice "tras 30 días" (inclusivo) y "supera 180 días" (estrictamente mayor). Se fija con tests de frontera en T-07 y T-08. |
| **D-04** | Los días se calculan sobre fecha de negocio en `America/Lima`, aunque la persistencia sea UTC. | Evita el desfase de un día en los umbrales; se aísla en T-04 para que ninguna otra tarea repita la conversión. |
| **D-05** | El correlativo sale de `code_counters`, no de `MAX(id)+1` ni del `id`. | Evita reutilizar códigos tras un borrado y mantiene la asignación atómica (T-15). |
| **D-06** | En `lookup`, si llegan `internal_code` y `serial_number`, el código tiene precedencia. | El código es la identidad fuerte (RN-02); el serial es opcional y puede repetirse. Se fija con test en T-20. |
| **D-07** | No hay job automático de abandono: los candidatos se calculan al consultar y la transición es manual con `confirm=true`. | La spec dice "puede marcarse" / "se marca" y RN-10 exige confirmación; automatizarlo introduciría un actor que la spec no define. |
| **D-08** | Sin Alembic: el esquema se crea con `create_all()`. | Decisión vigente del plan §1.3; una migración real queda fuera del alcance de esta entrega. |
| **D-09** | "Diagnóstico" es un dato sembrado en `operation_types`, no una rama de código. | Cierra el flujo de rechazo sin falsear datos (RN-03) y mantiene el maestro administrable como cualquier otro. |
| **D-10** | Se agrega `tests/integration/api/test_health_api.py`, no listado en el plan §1.3. | El primer corte vertical (T-10) necesita un punto de entrada observable; el router de salud sí está previsto en la estructura. |

### 12.2 Riesgos

| ID | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| **R-01** | RF-03 exige "muestro su historial previo", pero el historial completo llega en T-30. | Criterio de aceptación parcialmente abierto durante la fase 4. | Declarado en T-20 (`previous_services_count`); cierre formal en T-30. No se reporta RF-03 como completo antes. |
| **R-02** | La matriz de 15 aristas es un dato duplicado entre test y código. | Un cambio futuro de la spec deja tests y máquina desalineados. | Los tests enumeran las 15 válidas y las 85 inválidas desde una única tabla de referencia del test. |
| **R-03** | `Enum` con `native_enum=False` puede no emitir el `CHECK` si `create_constraint` queda desactivado. | La BD aceptaría estados fuera de los 10. | T-13 prueba insertando un valor inválido, no leyendo el DDL. |
| **R-04** | La cobertura ≥ 80 % en `app/services` depende de los tests de API; ramas como la baja de un maestro en uso pueden quedar sin cubrir. | La puerta de cobertura falla en T-37 y bloquea el cierre. | T-16 cubre la baja de maestro en uso con doble de repositorio; T-21 cubre `equipment_source_invalid` por API. |
| **R-05** | SQLite no preserva la zona horaria de `DateTime(timezone=True)`. | Umbrales desfasados un día si se lee sin normalizar. | Toda lectura pasa por la base temporal de T-04; ninguna tarea compara fechas en crudo. |
| **R-06** | `UNIQUE(origin_service_id)` impide un segundo reingreso vinculado al mismo origen. | Un tercer ingreso por la misma falla no puede apuntar al servicio original. | El segundo reingreso se vincula al primero (decisión del técnico, RN-04); se explica en la UI de T-33 y en el README de T-36. |
| **R-07** | T-21 y T-22 son las dos tareas L y concentran transacción, validaciones y bitácora. | Desborde de la fase 5 y de la ruta crítica. | Si se desbordan, se dividen por criterio de aceptación (recepción: XOR de equipo / historial inicial) sin alterar el orden de fases. |
| **R-08** | NFR-03 (5.000 registros) no se mide por tiempo para no introducir tests frágiles en CI. | Una regresión de rendimiento podría pasar desapercibida. | Se verifica ausencia de N+1 estructuralmente en T-28 y se documenta la medición manual en el README. |

---

## 13. Registro de cambios

| Versión | Fecha | Cambio |
|---|---|---|
| 1.0 | 22 de octubre de 2026 | Desglose inicial: 37 tareas en 7 fases y 2 iteraciones, derivado de `01-spec.md` y `02-plan.md` §4.6. |
