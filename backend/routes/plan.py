"""/plan/* — adaptive monthly planning: constraints, readiness, the plan itself.

All endpoints are JWT-gated. The backend uses the service-role Supabase key, so
the repositories scope every query by ``user_id`` themselves.

The plan is a derived cache: ``GET /plan/{period}`` recomputes from current
reality every call; ``POST .../recompute`` and ``POST /plan/readiness`` also
persist the prescriptions. See backend/planning.py + src/shared/planning/.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from backend.auth import authenticate_request
from backend.cache import invalidate_user
from backend.planning import build_and_store_plan, build_plan, period_for
from fastapi import APIRouter, Depends, HTTPException, Query, status
from src.shared.models.planning import (
    PlanConstraint,
    PlanConstraintRecord,
    PlanResult,
    Readiness,
)
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import (
    MetricTypesRepository,
    PlanConstraintsRepository,
    ReadinessRepository,
)

router = APIRouter(prefix="/plan", tags=["plan"])


def _today_local() -> date:
    """America/New_York anchor, consistent with /metrics and /stats."""
    return datetime.now(ZoneInfo("America/New_York")).date()


# ---------------------------------------------------------------- constraints


@router.post(
    "/constraints",
    response_model=PlanConstraintRecord,
    status_code=status.HTTP_201_CREATED,
)
async def create_constraint(
    body: PlanConstraint,
    user_id: UUID = Depends(authenticate_request),
) -> PlanConstraintRecord:
    supabase = get_supabase_client()
    if MetricTypesRepository(supabase).get(body.metric_key) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown metric_key '{body.metric_key}'")

    payload = body.model_dump(exclude_none=True, mode="json")
    row = PlanConstraintsRepository(supabase).create(user_id, payload)
    await invalidate_user(user_id)
    return PlanConstraintRecord(**row)


@router.get("/constraints", response_model=list[PlanConstraintRecord])
def list_constraints(
    user_id: UUID = Depends(authenticate_request),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> list[PlanConstraintRecord]:
    rows = PlanConstraintsRepository(get_supabase_client()).list(
        user_id, date_from=date_from, date_to=date_to
    )
    return [PlanConstraintRecord(**r) for r in rows]


@router.delete("/constraints/{constraint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_constraint(
    constraint_id: UUID,
    user_id: UUID = Depends(authenticate_request),
) -> None:
    deleted = PlanConstraintsRepository(get_supabase_client()).delete(user_id, constraint_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Constraint not found")
    await invalidate_user(user_id)


# ---------------------------------------------------------------- readiness


@router.post("/readiness", response_model=PlanResult)
async def set_readiness(
    body: Readiness,
    user_id: UUID = Depends(authenticate_request),
) -> PlanResult:
    """Record how the user feels and immediately recompute that day's month plan."""
    supabase = get_supabase_client()
    payload = body.model_dump(exclude_none=True, mode="json")
    ReadinessRepository(supabase).upsert(user_id, payload)
    await invalidate_user(user_id)
    return build_and_store_plan(supabase, user_id, period_for(body.log_on), _today_local())


# ---------------------------------------------------------------- the plan


@router.get("/{period}", response_model=PlanResult)
def get_plan(
    period: str,
    user_id: UUID = Depends(authenticate_request),
) -> PlanResult:
    """Recompute and return the plan for a ``YYYY-MM`` period (no persistence)."""
    try:
        return build_plan(get_supabase_client(), user_id, period, _today_local())
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/{period}/recompute", response_model=PlanResult)
async def recompute_plan(
    period: str,
    user_id: UUID = Depends(authenticate_request),
) -> PlanResult:
    """Recompute and persist the plan for a ``YYYY-MM`` period."""
    supabase = get_supabase_client()
    try:
        result = build_and_store_plan(supabase, user_id, period, _today_local())
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await invalidate_user(user_id)
    return result
