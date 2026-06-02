"""/metrics/* — generic metric tracking: catalog, entries, native goals.

All endpoints are JWT-gated. The backend uses the service-role Supabase key, so
the repositories scope every query by ``user_id`` themselves.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from backend.auth import authenticate_request
from backend.cache import invalidate_user
from backend.metrics_progress import compute_progress
from fastapi import APIRouter, Depends, HTTPException, Query, status
from src.shared.models.metric import (
    GoalProgress,
    MetricEntry,
    MetricEntryCreate,
    MetricGoal,
    MetricGoalCreate,
    MetricGoalUpdate,
    MetricType,
)
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import (
    MetricEntriesRepository,
    MetricGoalsRepository,
    MetricTypesRepository,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _today_local() -> date:
    """America/New_York anchor, consistent with /stats."""
    return datetime.now(ZoneInfo("America/New_York")).date()


# ---------------------------------------------------------------- types

@router.get("/types", response_model=list[MetricType])
def list_metric_types(
    _user_id: UUID = Depends(authenticate_request),
) -> list[MetricType]:
    rows = MetricTypesRepository(get_supabase_client()).list_all()
    return [MetricType(**r) for r in rows]


# ---------------------------------------------------------------- entries

@router.post("/entries", response_model=MetricEntry, status_code=status.HTTP_201_CREATED)
async def create_entry(
    body: MetricEntryCreate,
    user_id: UUID = Depends(authenticate_request),
) -> MetricEntry:
    supabase = get_supabase_client()
    if MetricTypesRepository(supabase).get(body.metric_key) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown metric_key '{body.metric_key}'")

    payload = body.model_dump(exclude_none=True)
    payload["occurred_on"] = (body.occurred_on or _today_local()).isoformat()
    if body.occurred_at is not None:
        payload["occurred_at"] = body.occurred_at.isoformat()

    row = MetricEntriesRepository(supabase).insert(user_id, payload)
    await invalidate_user(user_id)
    return MetricEntry(**row)


@router.get("/entries", response_model=list[MetricEntry])
def list_entries(
    user_id: UUID = Depends(authenticate_request),
    metric_key: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
) -> list[MetricEntry]:
    rows = MetricEntriesRepository(get_supabase_client()).list(
        user_id, metric_key=metric_key, date_from=date_from, date_to=date_to, limit=limit
    )
    return [MetricEntry(**r) for r in rows]


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: UUID,
    user_id: UUID = Depends(authenticate_request),
) -> None:
    deleted = MetricEntriesRepository(get_supabase_client()).delete(user_id, entry_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    await invalidate_user(user_id)


# ---------------------------------------------------------------- goals

def _progress_for(supabase, user_id: UUID, goal: MetricGoal) -> GoalProgress:
    metric = MetricTypesRepository(supabase).get(goal.metric_key)
    if metric is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Goal references unknown metric")
    # Pull the user's entries for this metric (recent history covers any window
    # plus the trailing days a streak needs).
    rows = MetricEntriesRepository(supabase).list(user_id, metric_key=goal.metric_key, limit=2000)
    entries = [MetricEntry(**r) for r in rows]
    return compute_progress(goal, MetricType(**metric), entries, _today_local())


@router.post("/goals", response_model=MetricGoal, status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: MetricGoalCreate,
    user_id: UUID = Depends(authenticate_request),
) -> MetricGoal:
    supabase = get_supabase_client()
    if MetricTypesRepository(supabase).get(body.metric_key) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown metric_key '{body.metric_key}'")

    payload = body.model_dump(exclude_none=True, mode="json")
    row = MetricGoalsRepository(supabase).create(user_id, payload)
    await invalidate_user(user_id)
    return MetricGoal(**row)


@router.get("/goals", response_model=list[GoalProgress])
def list_goals(
    user_id: UUID = Depends(authenticate_request),
    status_filter: str | None = Query(default="active", alias="status"),
) -> list[GoalProgress]:
    supabase = get_supabase_client()
    rows = MetricGoalsRepository(supabase).list(user_id, status=status_filter)
    return [_progress_for(supabase, user_id, MetricGoal(**r)) for r in rows]


@router.get("/goals/{goal_id}", response_model=GoalProgress)
def get_goal(
    goal_id: UUID,
    user_id: UUID = Depends(authenticate_request),
) -> GoalProgress:
    supabase = get_supabase_client()
    row = MetricGoalsRepository(supabase).get(user_id, goal_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    return _progress_for(supabase, user_id, MetricGoal(**row))


@router.patch("/goals/{goal_id}", response_model=MetricGoal)
async def update_goal(
    goal_id: UUID,
    body: MetricGoalUpdate,
    user_id: UUID = Depends(authenticate_request),
) -> MetricGoal:
    supabase = get_supabase_client()
    payload = body.model_dump(exclude_none=True, mode="json")
    row = MetricGoalsRepository(supabase).update(user_id, goal_id, payload)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    await invalidate_user(user_id)
    return MetricGoal(**row)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: UUID,
    user_id: UUID = Depends(authenticate_request),
) -> None:
    deleted = MetricGoalsRepository(get_supabase_client()).delete(user_id, goal_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    await invalidate_user(user_id)
