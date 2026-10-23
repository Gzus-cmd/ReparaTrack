# Frontend de ReparaTrack (Astro)

Interfaz web del sistema de trazabilidad de taller de **TerabyteRS**. Consume la
API de FastAPI (`/api/v1`) y sustituye visualmente a las vistas Jinja2, que se
mantienen intactas como respaldo.

## Requisitos

- Node.js 20.3 o superior (probado con Node 24).
- El backend FastAPI corriendo en `http://localhost:8000`.

## Puesta en marcha

```bash
# 1. Backend (desde la raíz del repositorio)
uvicorn app.main:app --reload --port 8000

# 2. Frontend (en otra terminal)
cd frontend
npm install
npm run dev
```

La aplicación queda en <http://localhost:4321>.

`npm run build` genera el servidor de producción en `dist/` y `npm run preview`
lo sirve en el mismo puerto.

## Configuración

| Variable        | Por defecto             | Uso                                                        |
| --------------- | ----------------------- | ---------------------------------------------------------- |
| `API_BASE_URL`  | `http://127.0.0.1:8000` | Origen que usa el **servidor** de Astro para pedir datos.  |

El navegador siempre llama a `/api/v1/...` en rutas relativas: en desarrollo el
proxy de Astro (`astro.config.mjs`) lo reenvía al backend y en producción se
espera un reverse proxy en el mismo origen. Si la API vive en otro origen, el
backend ya expone `CORSMiddleware` para `http://localhost:4321`.

## Estructura

```
src/
  components/   Piezas de UI reutilizables (navegación, badges, tablas, timeline)
  layouts/      Shell HTML con navegación y metadatos
  lib/          Cliente HTTP, contrato de estados y utilidades de formato
  pages/        Vistas (tablero, recepción, ficha, maestros, equipos, clientes)
  styles/       Design system en CSS puro (variables + componentes)
```

## Páginas

- `/` — tablero de equipos en taller con conteos por estado y alertas RN-07/RN-10.
- `/reception` — recepción de un equipo: cliente, equipo (existente o nuevo),
  falla, accesorios y condición física, con candidatos de garantía.
- `/service/[id]` — ficha del servicio: estado, evidencia de recepción, timeline,
  operaciones y transiciones permitidas.
- `/services` — bandeja completa de servicios con filtro por estado.
- `/equipments` — búsqueda y alta de equipos.
- `/equipments/[ref]` — historial técnico completo de un equipo.
- `/customers` — búsqueda y alta de clientes.
- `/customers/[id]` — ficha del cliente y sus servicios.
- `/catalogs` — administración de los cuatro maestros.
