# ReparaTrack — Sistema de Trazabilidad de Soporte Técnico

Software para el taller **TerabyteRS**: registra cada servicio de reparación con
trazabilidad completa por equipo y por cliente (recepción, diagnóstico, reparación,
entrega y garantía). Desarrollado con SDD + TDD (FastAPI, SQLAlchemy, SQLite, pytest).

- Documentación de diseño: `sdd/` (constitución, spec, plan, tasks)
- Código: `app/` · Tests: `tests/`

## Rama de desarrollo (GitFlow)

- `main` — producción
- `develop` — integración
- `testing` — pre-release / QA
- `feature/*` — nuevas funcionalidades (desde `develop`)
- `bugfix/*` / `hotfix/*` — correcciones (bugfix desde `develop`, hotfix desde `main`)
- `release/*` — preparación de versión
