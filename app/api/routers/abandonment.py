"""Router de abandono: candidatos por regla (RF-10 / T-34)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import ClockDep, SessionDep, build_abandonment_service
from app.api.schemas.abandonment import AbandonmentCandidateRead
from app.services.abandonment_service import AbandonmentCandidate

router = APIRouter(prefix="/abandonment", tags=["abandono"])


def _to_read(candidate: AbandonmentCandidate) -> AbandonmentCandidateRead:
    return AbandonmentCandidateRead(
        service_order_id=candidate.service_order_id,
        status=candidate.status,
        days_in_status=candidate.days_in_status,
        threshold_days=candidate.threshold_days,
        rule=candidate.rule,
        customer_name=candidate.customer_name,
        equipment_internal_code=candidate.equipment_internal_code,
    )


@router.get(
    "/candidates",
    response_model=list[AbandonmentCandidateRead],
    summary="Servicios que superan el umbral de abandono, agrupados por regla",
)
def list_abandonment_candidates(
    session: SessionDep,
    clock: ClockDep,
    rule: str | None = Query(
        default=None,
        description="Filtra un solo grupo: RN-10 (30 días) o RN-07 (más de 180 días).",
    ),
) -> list[AbandonmentCandidateRead]:
    """Devuelve los dos grupos sin mezclarlos; el abandono se marca manualmente."""
    candidates = build_abandonment_service(session, clock).candidates(rule=rule)
    return [_to_read(candidate) for candidate in candidates]
