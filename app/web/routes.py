"""Vistas HTML (Jinja2) de administración de maestros (T-17).

Las vistas consumen los mismos servicios que la API; ninguna regla se duplica.
Los formularios son HTML nativo (`application/x-www-form-urlencoded`), de modo
que la administración funciona sin JavaScript.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.api.deps import (
    ClockDep,
    SessionDep,
    build_catalog_service,
    build_customer_service,
    build_dashboard_service,
    build_equipment_service,
    build_service_detail_service,
    build_service_order_service,
)
from app.domain.enums import ServiceStatus
from app.domain.errors import DomainError
from app.services.service_order_service import NewEquipment

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["ui"])

CATALOG_SECTIONS: tuple[tuple[str, str], ...] = (
    ("device-types", "Tipos de dispositivo"),
    ("brands", "Marcas"),
    ("components", "Componentes"),
    ("operation-types", "Tipos de operación"),
)


# --- T-28: tablero de equipos en taller ---------------------------------------


@router.get("/", response_class=HTMLResponse, summary="Tablero de equipos en taller")
def dashboard_page(request: Request, session: SessionDep, clock: ClockDep) -> HTMLResponse:
    """Muestra los equipos en taller con su resumen por estado y sus alertas."""
    service = build_dashboard_service(session, clock)
    summary = service.summary()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "items": service.workbench(),
            "status_rows": [
                (status.label, summary.by_status[status.value]) for status in ServiceStatus
            ],
            "alerts": list(summary.alerts.values()),
        },
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


# --- T-27: recepción y ficha del servicio ------------------------------------


def _render_reception(
    request: Request, session: Session, *, error: str | None = None
) -> HTMLResponse:
    """Contexto completo del formulario de recepción (RF-04)."""
    customers = build_customer_service(session).search("", limit=200).items
    device_types = build_catalog_service("device-types", session).list_values()
    brands = build_catalog_service("brands", session).list_values()
    return templates.TemplateResponse(
        request,
        "reception.html",
        {
            "customers": customers,
            "device_types": device_types,
            "brands": brands,
            "error": error,
        },
    )


def _boolean(form: dict[str, str], field: str) -> bool:
    """Interpreta un checkbox HTML sin depender de JavaScript."""
    return form.get(field, "").strip().lower() in {"on", "true", "1", "yes"}


@router.get("/reception", response_class=HTMLResponse, summary="Formulario de recepción")
def reception_page(request: Request, session: SessionDep) -> HTMLResponse:
    """Muestra los cinco campos obligatorios de la recepción."""
    return _render_reception(request, session)


@router.post("/reception", summary="Recepción desde la vista")
async def create_reception_form(
    request: Request, session: SessionDep, clock: ClockDep
) -> Response:
    """Crea el servicio y redirige a su ficha; un error vuelve al formulario."""
    form = await _form_data(request)
    try:
        equipment_id: int | None
        new_equipment: NewEquipment | None
        if form.get("equipment_mode", "new") == "existing":
            equipment_id = build_equipment_service(session).lookup(
                internal_code=form.get("equipment_internal_code", "")
            ).id
            new_equipment = None
        else:
            equipment_id = None
            new_equipment = NewEquipment(
                device_type_id=int(form.get("new_device_type_id") or 0),
                brand_id=int(form.get("new_brand_id") or 0),
                model=form.get("new_model", ""),
                serial_number=(form.get("new_serial_number") or "").strip() or None,
            )
        order = build_service_order_service(session, clock).create(
            customer_id=int(form.get("customer_id") or 0),
            equipment_id=equipment_id,
            new_equipment=new_equipment,
            reported_failure=form.get("reported_failure", ""),
            accessories=form.get("accessories", ""),
            physical_condition=form.get("physical_condition", ""),
            password_requested=_boolean(form, "password_requested"),
        )
    except DomainError as exc:
        return _render_reception(request, session, error=exc.message)
    except ValueError:
        return _render_reception(
            request, session, error="Revise los datos del formulario e intente nuevamente."
        )
    return RedirectResponse(url=f"/service-orders/{order.id}", status_code=303)


# --- T-30: historial técnico del equipo ---------------------------------------


@router.get(
    "/equipments/{equipment_ref}/history",
    response_class=HTMLResponse,
    summary="Historial técnico completo del equipo",
)
def equipment_history_page(
    request: Request, equipment_ref: str, session: SessionDep
) -> HTMLResponse:
    """Muestra servicios, estados y detalles; acepta id, código interno o serial."""
    history = build_equipment_service(session).history(equipment_ref)
    return templates.TemplateResponse(
        request,
        "equipment_history.html",
        {"equipment": history.equipment, "services": history.services},
    )


@router.get(
    "/service-orders/{service_order_id}",
    response_class=HTMLResponse,
    summary="Ficha del servicio con historial y transiciones",
)
def service_order_page(
    request: Request, service_order_id: int, session: SessionDep, clock: ClockDep
) -> HTMLResponse:
    """Muestra estado, métricas, detalles, historial y botones permitidos."""
    service = build_service_order_service(session, clock)
    order = service.get(service_order_id)
    details = build_service_detail_service(session).list(service_order_id)
    return templates.TemplateResponse(
        request,
        "service_detail.html",
        {
            "order": order,
            "details": details,
            "history": service.history(service_order_id),
            "error": request.query_params.get("error"),
        },
    )


@router.post(
    "/service-orders/{service_order_id}/transitions",
    summary="Transición de estado desde la vista",
)
async def transition_from_ui(
    request: Request, service_order_id: int, session: SessionDep, clock: ClockDep
) -> RedirectResponse:
    """Ejecuta la transición o vuelve a la ficha con el motivo en español."""
    form = await _form_data(request)
    try:
        build_service_order_service(session, clock).transition(
            service_order_id,
            target=form.get("to_status", ""),
            comment=form.get("comment") or None,
            confirm=_boolean(form, "confirm"),
        )
    except DomainError as exc:
        return RedirectResponse(
            url=f"/service-orders/{service_order_id}?{urlencode({'error': exc.message})}",
            status_code=303,
        )
    return RedirectResponse(url=f"/service-orders/{service_order_id}", status_code=303)
