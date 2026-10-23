# Constitución — Sistema de Trazabilidad de Soporte Técnico

**Fecha:** 22 de octubre de 2026
**Negocio:** TerabyteRS
**Proyecto:** Sistema de Trazabilidad de Soporte Técnico (ReparaTrack)
**Equipo:** Jesús Antonio Caycho Sánchez y Leonardo Miguel Sanchez Ramos
**Curso:** Testing y Aseguramiento de la Calidad — VIII ciclo, UNDC

> Esta Constitución es el conjunto de principios **no negociables**. Ningún plan,
> tarea o línea de código puede contradecirla. Si surge una contradicción, se
> resuelve a favor de la Constitución y se revisa la spec.

## 1. Principios no negociables

1. **TDD estricto.** No se escribe código de producción sin un test que falle primero (RED → GREEN → REFACTOR).
2. **Dominio puro.** Las reglas de negocio y la máquina de estados viven en funciones/clases puras, sin entrada/salida, para testear en milisegundos.
3. **Máquina de estados cerrada.** Solo se permiten las transiciones definidas; cada cambio queda registrado en un historial inmutable (RN-05).
4. **Evidencia inmutable.** La condición física y los accesorios se fijan al recepcionar y **nunca** se editan (RN-08).
5. **Cero contraseñas.** Nunca se almacena la contraseña de un cliente; solo un indicador booleano de "solicitada" (RN-06).
6. **Identidad interna.** Cada equipo se identifica por **código interno correlativo**; el número de serie es opcional (RN-02).
7. **Trazabilidad total.** Cada requisito se enlaza: dolor → historia → regla → caso de prueba → resultado.
8. **Automatización.** Los tests corren en CI (GitHub Actions) en cada `push`.
9. **Una sola fuente de verdad.** `spec.md` es la verdad. Un cambio de requisito actualiza la spec y reabre sus tareas.
10. **Convenciones.** Identificadores y código en **inglés**; UI y mensajes en **español neutro**; estados en inglés (clave) con etiqueta en español.

## 2. Stack definitivo

Python 3.14 · **FastAPI** · **SQLAlchemy** · **SQLite** · **pytest** + pytest-cov · **Ruff** · **pre-commit** · **GitHub Actions** · Jinja2 (UI) · Swagger (`/docs`).

## 3. Definición de Hecho (DoD)

Una tarea está **hecha** cuando:
- Tests unitarios y de integración en **verde**.
- Cobertura ≥ **80 %** en dominio y servicios.
- **CI verde**.
- Swagger (`/docs`) refleja los endpoints.

## 4. Estados del servicio (10)

`RECEIVED` · `DIAGNOSING` · `AWAITING_APPROVAL` · `AWAITING_PART` · `IN_REPAIR` · `NOT_REPARABLE` · `REJECTED` · `READY_FOR_PICKUP` · `DELIVERED` · `ABANDONED`

## 5. Entorno de referencia

- Los tests de integración corren contra **SQLite** (archivo o en memoria) vía `TestClient`.
- UI responsive (celular + PC). Recepción objetivo ≤ 2 minutos, 5 campos obligatorios.
- Volumen de diseño: 50 equipos activos, 5.000 registros históricos sin degradación.
