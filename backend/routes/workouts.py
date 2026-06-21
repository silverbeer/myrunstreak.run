"""/workouts/* — Athlete Training Tracker: exercise catalog, templates, sessions.

JWT-gated; the backend uses the service-role key, so repositories scope every
query by ``user_id``. Templates and sessions are created with their children
(items / sets) inline and returned with them nested. See the Athlete Training
Tracker epic (SB-189).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from backend.admin import require_athlete_access
from backend.auth import authenticate_request
from backend.cache import invalidate_user
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from src.shared.models.workout import (
    Exercise,
    WorkoutSession,
    WorkoutSessionCreate,
    WorkoutTemplate,
    WorkoutTemplateCreate,
)
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import (
    ExercisesRepository,
    WorkoutSessionsRepository,
    WorkoutTemplatesRepository,
)

router = APIRouter(prefix="/workouts", tags=["workouts"])


def acting_athlete(
    user_id: UUID = Depends(authenticate_request),
    x_act_as_athlete: UUID | None = Header(default=None, alias="X-Act-As-Athlete"),
) -> UUID | None:
    """The athlete the caller is acting as (SB-198), or None for self.

    When set, the caller must have access to that athlete — so every workout
    operation below is scoped to an athlete the coach actually coaches.
    """
    if x_act_as_athlete is None:
        return None
    require_athlete_access(user_id, x_act_as_athlete)
    return x_act_as_athlete


# ---------------------------------------------------------------- catalog


@router.get("/exercises", response_model=list[Exercise])
def list_exercises(
    _user_id: UUID = Depends(authenticate_request),
) -> list[Exercise]:
    rows = ExercisesRepository(get_supabase_client()).list_all()
    return [Exercise(**r) for r in rows]


# ---------------------------------------------------------------- templates


@router.post("/templates", response_model=WorkoutTemplate, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: WorkoutTemplateCreate,
    user_id: UUID = Depends(authenticate_request),
    athlete_id: UUID | None = Depends(acting_athlete),
) -> WorkoutTemplate:
    supabase = get_supabase_client()
    valid = ExercisesRepository(supabase).keys()
    unknown = {i.exercise_key for i in body.items} - valid
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown exercise(s): {sorted(unknown)}")

    row = WorkoutTemplatesRepository(supabase).create(
        user_id, body.model_dump(mode="json", exclude_none=True), athlete_id=athlete_id
    )
    await invalidate_user(user_id)
    return WorkoutTemplate(**row)


@router.get("/templates", response_model=list[WorkoutTemplate])
def list_templates(
    user_id: UUID = Depends(authenticate_request),
    athlete_id: UUID | None = Depends(acting_athlete),
) -> list[WorkoutTemplate]:
    rows = WorkoutTemplatesRepository(get_supabase_client()).list(user_id, athlete_id=athlete_id)
    return [WorkoutTemplate(**r) for r in rows]


@router.get("/templates/{template_id}", response_model=WorkoutTemplate)
def get_template(
    template_id: UUID,
    user_id: UUID = Depends(authenticate_request),
    athlete_id: UUID | None = Depends(acting_athlete),
) -> WorkoutTemplate:
    row = WorkoutTemplatesRepository(get_supabase_client()).get(
        user_id, template_id, athlete_id=athlete_id
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return WorkoutTemplate(**row)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    user_id: UUID = Depends(authenticate_request),
    athlete_id: UUID | None = Depends(acting_athlete),
) -> None:
    if not WorkoutTemplatesRepository(get_supabase_client()).delete(
        user_id, template_id, athlete_id=athlete_id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    await invalidate_user(user_id)


# ---------------------------------------------------------------- sessions


@router.post("/sessions", response_model=WorkoutSession, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: WorkoutSessionCreate,
    user_id: UUID = Depends(authenticate_request),
    athlete_id: UUID | None = Depends(acting_athlete),
) -> WorkoutSession:
    supabase = get_supabase_client()
    valid = ExercisesRepository(supabase).keys()
    unknown = {s.exercise_key for s in body.sets} - valid
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown exercise(s): {sorted(unknown)}")

    row = WorkoutSessionsRepository(supabase).create(
        user_id, body.model_dump(mode="json", exclude_none=True), athlete_id=athlete_id
    )
    await invalidate_user(user_id)
    return WorkoutSession(**row)


@router.get("/sessions", response_model=list[WorkoutSession])
def list_sessions(
    user_id: UUID = Depends(authenticate_request),
    athlete_id: UUID | None = Depends(acting_athlete),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[WorkoutSession]:
    rows = WorkoutSessionsRepository(get_supabase_client()).list(
        user_id, date_from=date_from, date_to=date_to, limit=limit, athlete_id=athlete_id
    )
    return [WorkoutSession(**r) for r in rows]


@router.get("/sessions/{session_id}", response_model=WorkoutSession)
def get_session(
    session_id: UUID,
    user_id: UUID = Depends(authenticate_request),
    athlete_id: UUID | None = Depends(acting_athlete),
) -> WorkoutSession:
    row = WorkoutSessionsRepository(get_supabase_client()).get(
        user_id, session_id, athlete_id=athlete_id
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return WorkoutSession(**row)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    user_id: UUID = Depends(authenticate_request),
    athlete_id: UUID | None = Depends(acting_athlete),
) -> None:
    if not WorkoutSessionsRepository(get_supabase_client()).delete(
        user_id, session_id, athlete_id=athlete_id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    await invalidate_user(user_id)
