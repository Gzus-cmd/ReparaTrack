"""Vistas HTML (Jinja2) de administración de maestros (T-17).

Las vistas consumen los mismos servicios que la API; ninguna regla se duplica.
Los formularios son HTML nativo (`application/x-www-form-urlencoded`), de modo
que la administración funciona sin JavaScript.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.deps import SessionDep, build_catalog_service
from app.domain.errors import DomainError

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["ui"])

CATALOG_SECTIONS: tuple[tuple[str, str], ...] = (
    ("device-types", "Tipos de dispositivo"),
    ("brands", "Marcas"),
    ("components", "Componentes"),
    ("operation-types", "Tipos de operación"),
)


def _redirect(message: str | None = None) -> RedirectResponse:
    """Vuelve a la vista de maestros, con el mensaje de error si lo hubo."""
    location = "/catalogs" if message is None else f"/catalogs?{urlencode({'error': message})}"
    return RedirectResponse(url=location, status_code=303)


async def _form_data(request: Request) -> dict[str, str]:
    """Lee un formulario HTML urlencoded sin depender de `python-multipart`.

    Las plantillas usan el `enctype` por defecto
    (`application/x-www-form-urlencoded`), que se puede parsear con la
    biblioteca estándar; `python-multipart` solo hace falta para subir archivos.
    """
    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items() if values}


@router.get("/catalogs", response_class=HTMLResponse, summary="Administración de maestros")
def catalogs_page(request: Request, session: SessionDep) -> HTMLResponse:
    """Renderiza los cuatro maestros con sus valores y acciones disponibles."""
    sections = [
        {
            "slug": slug,
            "title": title,
            "entries": build_catalog_service(slug, session).list_values(include_inactive=True),
        }
        for slug, title in CATALOG_SECTIONS
    ]
    return templates.TemplateResponse(
        request,
        "catalogs.html",
        {"sections": sections, "error": request.query_params.get("error")},
    )


@router.post("/catalogs/{catalog}", summary="Alta de un valor desde la vista")
async def create_value_form(
    request: Request, catalog: str, session: SessionDep
) -> RedirectResponse:
    """Procesa el formulario de alta y vuelve a la vista."""
    form = await _form_data(request)
    name = form.get("name", "")
    try:
        build_catalog_service(catalog, session).create(name)
    except DomainError as exc:
        return _redirect(exc.message)
    return _redirect()


@router.post("/catalogs/{catalog}/{catalog_id}/deactivate", summary="Baja lógica desde la vista")
def deactivate_value_form(catalog: str, catalog_id: int, session: SessionDep) -> RedirectResponse:
    """Da de baja lógica un valor en uso sin borrarlo (RN-09)."""
    try:
        build_catalog_service(catalog, session).deactivate(catalog_id)
    except DomainError as exc:
        return _redirect(exc.message)
    return _redirect()


@router.post("/catalogs/{catalog}/{catalog_id}/activate", summary="Reactivación desde la vista")
def activate_value_form(catalog: str, catalog_id: int, session: SessionDep) -> RedirectResponse:
    """Reactiva un valor dado de baja."""
    try:
        build_catalog_service(catalog, session).activate(catalog_id)
    except DomainError as exc:
        return _redirect(exc.message)
    return _redirect()


@router.post("/catalogs/{catalog}/{catalog_id}/delete", summary="Borrado desde la vista")
def delete_value_form(catalog: str, catalog_id: int, session: SessionDep) -> RedirectResponse:
    """Borra un valor sin uso; si está en uso, la vista muestra el motivo."""
    try:
        build_catalog_service(catalog, session).delete(catalog_id)
    except DomainError as exc:
        return _redirect(exc.message)
    return _redirect()
