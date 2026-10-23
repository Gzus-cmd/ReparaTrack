# ReparaTrack — Sistema de Trazabilidad de Soporte Técnico

Software para el taller **TerabyteRS**: registra cada servicio de reparación con
trazabilidad completa por equipo y por cliente (recepción, diagnóstico, reparación,
entrega, garantía y abandono). Desarrollado con SDD + TDD sobre **FastAPI +
SQLAlchemy + SQLite + pytest**.

- Documentación de diseño: `sdd/` (constitución, spec, plan, tasks)
- Código: `app/` · Pruebas: `tests/` · Datos: `reparatrack.db` (SQLite)

## 1. Arranque rápido

Requisitos: Python 3.11 o superior (la integración continua usa 3.14) y `pip`.

```powershell
# 1. Entorno virtual e instalación de dependencias
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install fastapi sqlalchemy jinja2 uvicorn pytest pytest-cov httpx ruff

# 2. Arranque en modo desarrollo (crea el esquema si no existe)
py -m uvicorn app.main:create_app --factory --reload
```

Servicios disponibles al arrancar:

| URL | Contenido |
|---|---|
| `http://127.0.0.1:8000/` | Tablero "Equipos en taller" (RF-07) |
| `http://127.0.0.1:8000/reception` | Recepción de 5 campos con aviso de garantía (RF-04, RF-09) |
| `http://127.0.0.1:8000/catalogs` | Administración de maestros (RF-01) |
| `http://127.0.0.1:8000/api/v1/health` | Estado del servicio y de la base |
| `http://127.0.0.1:8000/docs` | Swagger UI con el contrato completo |

Configuración por entorno (valores por defecto entre paréntesis):
`DATABASE_URL` (`sqlite+pysqlite:///./reparatrack.db`), `WARRANTY_DAYS` (90),
`ABANDONMENT_DAYS` (180) y `APPROVAL_DAYS` (30). Sin esas variables el sistema
aplica los umbrales de la spec.

## 2. Comandos de calidad

El `pyproject.toml` fija las puertas del plan §4.5 en `addopts`: `-ra`, cobertura
con ramas (`--cov-branch`) y umbral del **80 %** (`--cov-fail-under=80`).

| Paso | Comando | Puerta |
|---|---|---|
| Lint | `py -m ruff check .` | 0 hallazgos |
| Formato | `py -m ruff format --check .` | sin cambios pendientes |
| Unitarias | `py -m pytest tests/unit -q --no-cov` | 100 % en verde, < 2 s |
| Integración | `py -m pytest tests/integration -q --no-cov` | 100 % en verde |
| Cobertura | `py -m pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=80 -q` | ≥ 80 % |
| Todo junto | `py -m pytest -q` | suite completa con la puerta de cobertura |

`--no-cov` solo hace falta en los pasos parciales: la cobertura de `tests/unit`
por separado no llega al 80 % y la puerta debe evaluarse sobre la suite completa.

La misma secuencia corre en GitHub Actions en cada `push` y `pull_request`
(`.github/workflows/ci.yml`); `.pre-commit-config.yaml` adelanta lint, formato y
unitarias antes de cada commit.

## 3. Respaldo de SQLite (NFR-05)

SQLite guarda **toda** la base en un único archivo (`reparatrack.db`). Copiarlo es
el respaldo completo; no hay servidor ni tablas externas que exportar.

```powershell
# Respaldo en caliente y consistente (recomendado, no requiere detener la app)
sqlite3 reparatrack.db ".backup 'respaldo\reparatrack-20261022.db'"

# Respaldo simple con la aplicación detenida
Copy-Item reparatrack.db "respaldo\reparatrack-$(Get-Date -Format yyyyMMdd-HHmm).db"
```

Recomendaciones:

1. Guarde un respaldo por semana y antes de cada actualización del sistema.
2. Mantenga los respaldos fuera del directorio del proyecto (y del repositorio).
3. Para restaurar, detenga la aplicación y reemplace `reparatrack.db` por la copia.
4. Verifique la copia abriéndola en solo lectura:
   `sqlite3 respaldo\reparatrack-20261022.db "select count(*) from service_orders;"`.

## 4. Reglas de negocio implementadas

| Regla | Comportamiento |
|---|---|
| RN-03 | `READY_FOR_PICKUP` exige al menos una línea de detalle. |
| RN-04 | Garantía de **90 días** desde la entrega: el sistema **alerta** con candidatos y el **técnico decide** si vincula. No se compara el texto de las fallas. |
| RN-05 | Solo las 15 aristas de la matriz; cada cambio queda en la bitácora. |
| RN-07 | `READY_FOR_PICKUP` con **más de 180 días** habilita el abandono. |
| RN-08 | La condición física se fija en la recepción y es inmutable. |
| RN-10 | `AWAITING_APPROVAL` con **30 días o más** habilita el abandono. |

El abandono (`ABANDONED`) es **siempre manual y confirmado** (`confirm=true`): no
existe un job automático. `GET /api/v1/abandonment/candidates` devuelve los dos
grupos separados (RN-10 y RN-07) y acepta `?rule=RN-10` o `?rule=RN-07`.

**Reingresos vinculados (riesgo R-06):** `service_orders.origin_service_id` es
único, de modo que un servicio de origen admite **un solo** reingreso vinculado. Si
el equipo vuelve a fallar, el nuevo servicio se vincula **al reingreso anterior**.
Un segundo intento contra el mismo origen responde `409 origin_already_linked`; la
vista de recepción muestra el mismo aviso antes de enviar el formulario.

## 5. Contrato de la API

Base: `/api/v1`. Los errores usan siempre el envelope
`{"error": {"code", "message", "details"}}` (código estable en inglés, mensaje en
español neutro). Swagger documenta cada endpoint con su resumen en español.

| Requisito | Endpoints principales |
|---|---|
| RF-01 Maestros | `GET/POST/PATCH/DELETE /catalogs/{catalog}` |
| RF-02 Clientes | `GET/POST/PATCH /customers`, `GET /customers/{id}/history` |
| RF-03 Equipos | `POST /equipments`, `GET /equipments/lookup` |
| RF-04 Recepción | `POST /service-orders` |
| RF-05 Operaciones | `GET/POST/DELETE /service-orders/{id}/details` |
| RF-06 Estados | `POST /service-orders/{id}/transitions`, `GET .../history` |
| RF-07 Tablero | `GET /dashboard/workbench`, `GET /dashboard/summary` |
| RF-08 Historial | `GET /equipments/{id}/history` |
| RF-09 Garantía | `GET /warranty/candidates`, `GET /warranty/eligibility` |
| RF-10 Abandono | `GET /abandonment/candidates`, `POST .../transitions` → `ABANDONED` |

La matriz de trazabilidad RF → tareas → pruebas vive en `sdd/03-tasks.md` §11.

## 6. Estructura del proyecto

```text
app/
  api/          routers, esquemas Pydantic, dependencias y envelope de error
  db/           modelos SQLAlchemy, semilla y repositorios SQL
  domain/       enums, matriz de estados, reglas puras, códigos y errores
  services/     casos de uso (puertos + servicios); no importan FastAPI ni SQLAlchemy
  templates/    vistas Jinja2 (funcionan sin JavaScript)
  web/          rutas HTML que consumen los mismos servicios que la API
sdd/            constitución, spec, plan y desglose de tareas
tests/
  unit/         dominio puro, sin base de datos ni reloj real
  integration/  repositorios y API con TestClient sobre SQLite en memoria
  support/      reloj congelado y factories deterministas
```

## 7. Flujo de ramas (GitFlow)

- `main` — producción
- `develop` — integración
- `testing` — pre-release / QA
- `feature/*` — nuevas funcionalidades (desde `develop`)
- `bugfix/*` / `hotfix/*` — correcciones (bugfix desde `develop`, hotfix desde `main`)
- `release/*` — preparación de versión
