# Especificación (Spec) — Sistema de Trazabilidad de Soporte Técnico

**Versión:** 1.0 · **Fecha:** 22 de octubre de 2026

> Fuente de verdad del proyecto. Todo lo que se implemente debe trazarse a esta
> spec. Los requisitos se normalizaron resolviendo las contradicciones entre
> `requerimientos-core-taller.pdf` y `Informe_Requerimientos_Testing_UNDC.docx`
> (este último manda; el PDF queda como anexo histórico).

## 1. Objetivo y contexto

Negocio unipersonal de reparación de laptops, PCs e impresoras, operado por un único
técnico (dueño). Hoy no existe ningún registro formal: todo se lleva de memoria. El
sistema **crea** el proceso de registro, no automatiza uno existente.

**Dolores:**
- **D1** — Los clientes llaman a preguntar en qué estado está su equipo cuando pasa más de un día.
- **D2** — No recuerda qué le hizo a un equipo que ya atendió antes.
- **D3** — Olvida comprar consumibles (fuera de alcance, documentado).

## 2. Actores

- **Técnico** (único usuario). No hay autenticación ni roles (fuera de alcance).

## 3. Glosario

| Término | Significado |
|---|---|
| Equipo | Instancia física de hardware (laptop, PC o impresora). |
| Servicio | Orden de atención a un equipo: recepción, diagnóstico, reparación y entrega. |
| Detalle | Línea de trabajo realizada (operación + componente opcional + descripción). |
| Historial de estados | Bitácora inmutable de cambios de estado con fecha y hora. |
| Reingreso | Equipo que vuelve por la misma falla dentro de la garantía. |
| "Robado" (tornillo) | Jerga de taller: tornillo con ranura barrida/desgastada (no connota delito). |

## 4. Alcance

**Dentro:** maestros (tipo dispositivo, marca, componente, operación), clientes,
equipos, servicios con detalle, ciclo de estados + historial, consulta de historial
por equipo y por cliente.

**Fuera (decisiones explícitas):** dinero/facturación, autenticación/roles, colas y
priorización, inventario de consumibles (D3), piezas recuperadas, almacenamiento de
contraseñas.

## 5. Modelo de dominio (entidades y atributos)

- **TipoDispositivo** — `id`, `nombre` (laptop, PC, impresora).
- **Marca** — `id`, `nombre`.
- **Componente** — `id`, `nombre` (RAM, disco, pasta térmica, pad térmico…).
- **TipoOperacion** — `id`, `nombre` (mantenimiento, reparación, diagnóstico, cambio, formateo, migración).
- **Cliente** — `id`, `nombre`, `telefono`, `correo`, `documento` (dato diferenciador).
- **Equipo** — `id`, `codigo_interno` (único, correlativo), `tipo_dispositivo_id`, `marca_id`, `modelo`, `numero_serie` (opcional). *No* tiene dueño: la propiedad se registra por servicio.
- **Servicio** — `id`, `equipo_id`, `cliente_id`, `fecha_recepcion`, `falla_reportada`, `condicion_fisica` (inmutable), `accesorios`, `contrasena_solicitada` (bool), `estado`, `fecha_entrega`, `servicio_origen_id` (nullable, para garantía).
- **DetalleServicio** — `id`, `servicio_id`, `tipo_operacion_id`, `componente_id` (opcional), `descripcion`.
- **HistorialEstado** — `id`, `servicio_id`, `estado`, `fecha_hora`, `comentario` (opcional).

> **Decisión normalizada:** la relación Cliente–Equipo **no** vive en Equipo sino en
> Servicio. Si un equipo se vende y reingresa por otra persona, el historial técnico
> persiste y el servicio actual se asocia al nuevo cliente.

## 6. Máquina de estados (10 estados)

```
RECEIVED ──► DIAGNOSING ──┬─► AWAITING_APPROVAL ──┬─► IN_REPAIR ──┬─► READY_FOR_PICKUP ──┬─► DELIVERED
                          │                        ├─► REJECTED ──► DELIVERED             └─► ABANDONED
                          ├─► AWAITING_PART ───────┴─► IN_REPAIR
                          └─► NOT_REPARABLE ───────► DELIVERED
```

Matriz de transiciones válidas:

| Origen | Destinos válidos |
|---|---|
| `RECEIVED` | `DIAGNOSING` |
| `DIAGNOSING` | `AWAITING_APPROVAL`, `AWAITING_PART`, `NOT_REPARABLE` |
| `AWAITING_APPROVAL` | `IN_REPAIR`, `REJECTED`, `ABANDONED` (tras 30 días sin respuesta) |
| `AWAITING_PART` | `IN_REPAIR` |
| `IN_REPAIR` | `READY_FOR_PICKUP`, `AWAITING_PART` (iterativo) |
| `NOT_REPARABLE` | `DELIVERED` |
| `REJECTED` | `DELIVERED` |
| `READY_FOR_PICKUP` | `DELIVERED`, `ABANDONED`, `IN_REPAIR` (retrabajo) |
| `DELIVERED` | (terminal; permite reingreso → nuevo servicio vinculado) |
| `ABANDONED` | (terminal) |

## 7. Reglas de negocio (RN)

- **RN-01** — Un servicio corresponde a exactamente un equipo. Dos equipos el mismo día generan dos servicios.
- **RN-02** — Un equipo se identifica por **código interno correlativo único**. El serial es opcional.
- **RN-03** — Un servicio debe tener **≥ 1 línea de detalle** para pasar a `READY_FOR_PICKUP`. "Diagnóstico" es una operación válida (cierra el flujo de rechazo sin falsear datos).
- **RN-04** — Garantía de **90 días** desde la fecha de entrega. El sistema **alerta**; el técnico **decide** la vinculación (juicio humano sobre "misma falla").
- **RN-05** — Solo se permiten las transiciones de la matriz; cada cambio queda registrado con fecha y hora.
- **RN-06** — Se registra si se solicitó la contraseña (bool), **nunca** su valor.
- **RN-07** — Un servicio en `READY_FOR_PICKUP` que supera **180 días** se marca `ABANDONED`.
- **RN-08** — La condición física se registra en recepción y es **inmutable** (evidencia ante reclamos).
- **RN-09** — Los maestros son administrables desde la aplicación (CRUD); no se elimina un valor en uso, se desactiva.
- **RN-10** — Un servicio en `AWAITING_APPROVAL` sin respuesta durante **30 días** puede marcarse `ABANDONED` (transición manual con confirmación).

## 8. Requisitos funcionales y criterios de aceptación

| ID | Historia | Criterios de aceptación (Gherkin) |
|---|---|---|
| RF-01 | HU-01 Maestros | Dado un valor existente, cuando intento duplicarlo, entonces se rechaza. Dado un valor en uso, cuando intento eliminarlo, entonces se desactiva en vez de borrar. |
| RF-02 | HU-02 Clientes | Dado un cliente nuevo, cuando lo registro, entonces queda con su contacto. |
| RF-03 | HU-03 Equipos | Dado un equipo nuevo, cuando lo registro, entonces se genera un código interno único. Dado un código/serial conocido, cuando ingreso el equipo, entonces muestro su historial previo. |
| RF-04 | HU-04 Recepción | Dados falla, accesorios, contraseña y condición física, cuando recepciono, entonces se crea un servicio en `RECEIVED` con fecha/hora. Dado sin falla reportada, cuando recepciono, entonces se rechaza e indica el campo faltante. |
| RF-05 | HU-05 Operaciones | Dado un servicio en `IN_REPAIR`, cuando registro operaciones con componente, entonces quedan como líneas de detalle. Dado sin líneas, cuando paso a `READY_FOR_PICKUP`, entonces se impide. |
| RF-06 | HU-06 Estados | Dada una transición válida, cuando la ejecuto, entonces se actualiza el estado y se registra en historial. Dada una inválida, cuando la intento, entonces se rechaza y el estado no cambia. |
| RF-07 | HU-07 Dashboard | Dados servicios sin entregar, cuando abro "equipos en taller", entonces veo cliente, estado y días transcurridos. |
| RF-08 | HU-08 Historial | Dado un equipo con servicios previos, cuando consulto, entonces veo el historial completo. |
| RF-09 | HU-09 Garantía | Dado un servicio entregado hace < 90 días, cuando reingreso por la misma falla, entonces se ofrece vincular al original. Dado ≥ 90 días, entonces es servicio nuevo. |
| RF-10 | HU-10 Abandono | Dados servicios listos o en espera que superan el umbral, cuando consulto, entonces los identifico para marcar `ABANDONED`. |

## 9. Requisitos no funcionales (NFR)

| ID | NFR | Criterio medible |
|---|---|---|
| NFR-01 | Velocidad de recepción | ≤ 2 minutos con 5 campos obligatorios. |
| NFR-02 | Portabilidad / responsive | Uso en celular y PC. |
| NFR-03 | Capacidad | 50 equipos activos y 5.000 registros históricos sin degradación. |
| NFR-04 | Seguridad | Sin autenticación (aceptado); sin almacenamiento de contraseñas (RN-06). |
| NFR-05 | Respaldo | SQLite es un archivo; se documenta copia/exportación periódica. |
| NFR-06 | Automatización | CI (GitHub Actions) corre lint + tests en cada push. |

## 10. Decisiones normalizadas (resumen)

1. Identidad por código interno correlativo; serial opcional.
2. Relación Cliente–Equipo vía Servicio.
3. 10 estados (no 9).
4. Garantía: el sistema alerta, el técnico decide.
5. Abandono: 180 días desde `READY_FOR_PICKUP` + 30 días sin respuesta en `AWAITING_APPROVAL`.
6. "Diagnóstico" es operación válida → el rechazo cierra sin falsear datos.
7. `READY_FOR_PICKUP → IN_REPAIR` permitido (retrabajo).
8. Stack: Python + FastAPI + SQLAlchemy + SQLite + pytest.
