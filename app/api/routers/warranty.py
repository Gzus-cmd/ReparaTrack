"""Router de garantía: candidatos y elegibilidad (RF-09 / T-32)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ClockDep, SessionDep, build_warranty_service
from app.api.schemas.warranty import WarrantyCandidateRead, WarrantyEligibilityRead
from app.services.warranty_service import WarrantyCandidate, WarrantyEvaluation

router = APIRouter(prefix="/warranty", tags=["garantía"])


def _candidate_to_read(candidate: WarrantyCandidate) -> WarrantyCandidateRead:
    return WarrantyCandidateRead(
        service_order_id=candidate.service_order_id,
        delivered_at=candidate.delivered_at,
        days_since_delivery=candidate.days_since_delivery,
        warranty_days_left=candidate.warranty_days_left,
        reported_failure=candidate.reported_failure,
    )


def _evaluation_to_read(evaluation: WarrantyEvaluation) -> WarrantyEligibilityRead:
    return WarrantyEligibilityRead(
        eligible=evaluation.eligible,
        days_since_delivery=evaluation.days_since_delivery,
        reason=evaluation.reason,
    )


@router.get(
    "/candidates",
    response_model=list[WarrantyCandidateRead],
    summary="Servicios entregados dentro de la garantía de un equipo",
)
def list_warranty_candidates(
    session: SessionDep,
    clock: ClockDep,
    equipment_id: Annotated[
        int, Query(gt=0, description="Equipo cuyos servicios entregados se evalúan.")
    ],
    as_of: Annotated[
        datetime | None,
        Query(description="Instante de evaluación; por defecto, el reloj del sistema."),
    ] = None,
) -> list[WarrantyCandidateRead]:
    """Alerta sobre los reingresos posibles; el técnico decide si vincula (RN-04)."""
    candidates = build_warranty_service(session, clock).candidates(
        equipment_id=equipment_id, as_of=as_of
    )
    return [_candidate_to_read(candidate) for candidate in candidates]


@router.get(
    "/eligibility",
    response_model=WarrantyEligibilityRead,
    summary="Evalúa si un servicio de origen sigue en garantía",
)
def get_warranty_eligibility(
    session: SessionDep,
    clock: ClockDep,
    origin_service_id: Annotated[int, Query(gt=0, description="Servicio de origen que se evalúa.")],
    as_of: Annotated[
        datetime | None,
        Query(description="Instante de evaluación; por defecto, el reloj del sistema."),
    ] = None,
) -> WarrantyEligibilityRead:
    """Devuelve elegibilidad, días transcurridos y motivo; el origen debe existir."""
    evaluation = build_warranty_service(session, clock).eligibility(
        origin_service_id=origin_service_id, as_of=as_of
    )
    return _evaluation_to_read(evaluation)
