"""Router del tablero "equipos en taller" (RF-07 / T-28)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import ClockDep, SessionDep, build_dashboard_service
from app.api.schemas.dashboard import (
    AlertGroupRead,
    DashboardSummaryRead,
    WorkbenchItemRead,
    WorkbenchRead,
)
from app.services.dashboard_service import AlertGroup, DashboardSummary, WorkbenchItem

router = APIRouter(prefix="/dashboard", tags=["tablero"])


def _to_read(item: WorkbenchItem) -> WorkbenchItemRead:
    return WorkbenchItemRead(
        service_order_id=item.service_order_id,
        customer_name=item.customer_name,
        equipment_internal_code=item.equipment_internal_code,
        device_type=item.device_type,
        status=item.status,
        status_label=item.status_label,
        received_at=item.received_at,
        days_since_reception=item.days_since_reception,
        days_in_status=item.days_in_status,
        is_over_threshold=item.is_over_threshold,
        threshold_rule=item.threshold_rule,
    )


def _group_to_read(group: AlertGroup) -> AlertGroupRead:
    return AlertGroupRead(
        rule=group.rule,
        threshold_days=group.threshold_days,
        count=group.count,
        service_order_ids=list(group.service_order_ids),
    )


def _summary_to_read(summary: DashboardSummary) -> DashboardSummaryRead:
    return DashboardSummaryRead(
        by_status=summary.by_status,
        alerts={code: _group_to_read(group) for code, group in summary.alerts.items()},
    )


@router.get(
    "/workbench",
    response_model=WorkbenchRead,
    summary="Equipos en taller con cliente, estado y días transcurridos",
)
def get_workbench(
    session: SessionDep,
    clock: ClockDep,
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filtra por estado; los terminales no están en taller.",
    ),
) -> WorkbenchRead:
    """Devuelve los servicios sin entregar ordenados por días descendente."""
    items = build_dashboard_service(session, clock).workbench(status=status_filter)
    return WorkbenchRead(items=[_to_read(item) for item in items])


@router.get(
    "/summary",
    response_model=DashboardSummaryRead,
    summary="Conteo por estado y alertas de umbral separadas por regla",
)
def get_summary(session: SessionDep, clock: ClockDep) -> DashboardSummaryRead:
    """Devuelve las diez claves de estado y los grupos RN-07/RN-10."""
    return _summary_to_read(build_dashboard_service(session, clock).summary())
