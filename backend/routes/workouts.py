"""/workouts/* — Athlete Training Tracker: exercise catalog, templates, sessions.

JWT-gated; the backend uses the service-role key, so repositories scope every
query by ``user_id``. Templates and sessions are created with their children
(items / sets) inline and returned with them nested. See the Athlete Training
Tracker epic (SB-189).
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from backend.admin import coaches_athlete, is_admin, require_athlete_access
from backend.auth import authenticate_request
from backend.cache import invalidate_user
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from src.shared.models.workout import (
    Exercise,
    ExerciseCreate,
    ExerciseUpdate,
    WorkoutSchedule,
    WorkoutScheduleCreate,
    WorkoutSession,
    WorkoutSessionCreate,
    WorkoutSessionUpdate,
    WorkoutTemplate,
    WorkoutTemplateCreate,
)
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import (
    ExercisesRepository,
    WorkoutScheduleRepository,
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


def _require_may_modify(
    user_id: UUID, athlete_id: UUID | None, row: dict[str, Any], kind: str
) -> None:
    """Enforce who may change an athlete-scoped row (SB-486).

    A coach may modify anything belonging to an athlete they coach. Anyone else
    with access — which means the athlete themselves — may modify only what
    they authored. So Matthew's prescription stays authoritative: Gabe can log
    against it and print it, but not rewrite it.

    Hiding the buttons is not enforcement; without this an athlete could PATCH a
    coach's template directly. A NULL ``created_by`` predates athlete-authored
    rows and is treated as the coach's.
    """
    if athlete_id is None:
        return  # self-owned rows: _scope already limits these to the caller
    if coaches_athlete(user_id, athlete_id):
        return
    created_by = row.get("created_by")
    if created_by and UUID(str(created_by)) == user_id:
        return
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        f"This {kind} was created by your coach — you can use it, but not change it",
    )


@router.get("/exercises", response_model=list[Exercise])
def list_exercises(
    user_id: UUID = Depends(authenticate_request),
) -> list[Exercise]:
    """The catalog the caller can use: the public library + their own private ones."""
    rows = ExercisesRepository(get_supabase_client()).list_visible(user_id)
    return [Exercise(**r) for r in rows]


@router.get("/exercises/search", response_model=list[Exercise])
def search_exercises(
    q: str = Query(..., min_length=1, description="Fuzzy match over name + aliases"),
    user_id: UUID = Depends(authenticate_request),
) -> list[Exercise]:
    """Search-first selection + dedup: find existing exercises before creating one."""
    rows = ExercisesRepository(get_supabase_client()).search(user_id, q)
    return [Exercise(**r) for r in rows]


def _duplicate_conflict(candidates: list[dict[str, Any]], message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={
            "message": message,
            "candidates": [
                {
                    "key": c["key"],
                    "display_name": c["display_name"],
                    "visibility": c.get("visibility"),
                    "aliases": c.get("aliases") or [],
                }
                for c in candidates
            ],
        },
    )


@router.post("/exercises", response_model=Exercise, status_code=status.HTTP_201_CREATED)
def create_exercise(
    body: ExerciseCreate,
    force: bool = False,
    user_id: UUID = Depends(authenticate_request),
) -> Exercise:
    """Add a coach-owned exercise (private by default; publishable later).

    Guards against duplicates (SB-454): if the catalog already holds this
    movement under any spelling, returns 409 with the candidates rather than
    silently creating a second row under a `_2` slug. Pass ?force=true when it
    genuinely is a distinct movement.
    """
    repo = ExercisesRepository(get_supabase_client())
    if not force:
        dups = repo.find_possible_duplicates(user_id, body.display_name, body.aliases)
        if dups:
            raise _duplicate_conflict(
                dups,
                "An exercise with this name already exists. Use it instead of "
                "adding a second row for the same movement — or resubmit with "
                "force=true if this is genuinely different.",
            )
    payload = body.model_dump(exclude_none=True, mode="json")
    row = repo.create(user_id, payload)
    return Exercise(**row)


@router.patch("/exercises/{key}", response_model=Exercise)
def update_exercise(
    key: str,
    body: ExerciseUpdate,
    user_id: UUID = Depends(authenticate_request),
) -> Exercise:
    """Patch an exercise. A coach may patch only their own; an admin may patch
    any, including the canonical library (404 if not found or not permitted)."""
    patch = body.model_dump(exclude_none=True, mode="json")
    row = ExercisesRepository(get_supabase_client()).update(
        user_id, key, patch, is_admin=is_admin(user_id)
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercise not found or not yours")
    return Exercise(**row)


@router.post("/exercises/{key}/publish", response_model=Exercise)
def publish_exercise(
    key: str,
    force: bool = False,
    user_id: UUID = Depends(authenticate_request),
) -> Exercise:
    """Promote an owned private exercise to the public library.

    This is the publish-time near-duplicate warning the catalog migration
    promised (SB-454): if the shared library already has this movement, 409 with
    the candidates instead of adding a second public row. ?force=true overrides.
    """
    repo = ExercisesRepository(get_supabase_client())
    if not force:
        own = repo.get(key)
        if own is not None:
            dups = repo.find_possible_duplicates(
                user_id, own["display_name"], own.get("aliases"), public_only=True
            )
            if dups:
                raise _duplicate_conflict(
                    dups,
                    "The public library already has this movement. Publishing "
                    "would create a second canonical row — resubmit with "
                    "force=true if it is genuinely distinct.",
                )
    row = repo.publish(user_id, key)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercise not found or not yours")
    return Exercise(**row)


@router.delete("/exercises/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(
    key: str,
    user_id: UUID = Depends(authenticate_request),
) -> None:
    """Delete an exercise the caller owns (404 if not found or not theirs)."""
    if not ExercisesRepository(get_supabase_client()).delete(user_id, key):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercise not found or not yours")


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


@router.patch("/templates/{template_id}", response_model=WorkoutTemplate)
async def update_template(
    template_id: UUID,
    body: WorkoutTemplateCreate,
    user_id: UUID = Depends(authenticate_request),
    athlete_id: UUID | None = Depends(acting_athlete),
) -> WorkoutTemplate:
    supabase = get_supabase_client()
    valid = ExercisesRepository(supabase).keys()
    unknown = {i.exercise_key for i in body.items} - valid
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown exercise(s): {sorted(unknown)}")

    existing = WorkoutTemplatesRepository(supabase).get(user_id, template_id, athlete_id=athlete_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found or not yours")
    _require_may_modify(user_id, athlete_id, existing, "workout")

    row = WorkoutTemplatesRepository(supabase).update(
        user_id, template_id, body.model_dump(mode="json", exclude_none=True), athlete_id=athlete_id
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found or not yours")
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
    repo = WorkoutTemplatesRepository(get_supabase_client())
    existing = repo.get(user_id, template_id, athlete_id=athlete_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    _require_may_modify(user_id, athlete_id, existing, "workout")

    if not repo.delete(user_id, template_id, athlete_id=athlete_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    await invalidate_user(user_id)


# ---------------------------------------------------------------- schedule


@router.post("/schedule", response_model=WorkoutSchedule, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: WorkoutScheduleCreate,
    user_id: UUID = Depends(authenticate_request),
    athlete_id: UUID | None = Depends(acting_athlete),
) -> WorkoutSchedule:
    """Put a plan on a day (SB-534).

    Either side may: the coach assigning Thursday, or the athlete planning their
    own week. Both are authorised identically — ``acting_athlete`` already
    accepts the coach and the linked athlete — and the row records which of them
    it was, because the screen has to say.
    """
    supabase = get_supabase_client()
    template = WorkoutTemplatesRepository(supabase).get(
        user_id, body.template_id, athlete_id=athlete_id
    )
    # Scheduling something you cannot see would leak its existence, and a
    # dangling schedule row renders as a blank card.
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")

    row = WorkoutScheduleRepository(supabase).create(
        user_id, body.model_dump(mode="json", exclude_none=True), athlete_id=athlete_id
    )
    await invalidate_user(user_id)
    return WorkoutSchedule(**row)


@router.get("/schedule", response_model=list[WorkoutSchedule])
def list_schedule(
    user_id: UUID = Depends(authenticate_request),
    athlete_id: UUID | None = Depends(acting_athlete),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> list[WorkoutSchedule]:
    """Planned occasions in date order. Callers filter the window they want —
    Coming up asks from today, a calendar would ask for a month."""
    rows = WorkoutScheduleRepository(get_supabase_client()).list(
        user_id, date_from=date_from, date_to=date_to, athlete_id=athlete_id
    )
    return [WorkoutSchedule(**r) for r in rows]


@router.delete("/schedule/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: UUID,
    user_id: UUID = Depends(authenticate_request),
    athlete_id: UUID | None = Depends(acting_athlete),
) -> None:
    """Unschedule an occasion.

    The same split as everything else athlete-scoped (SB-486): a coach may
    remove anything on their athlete's calendar; the athlete may remove what
    they put there themselves, and not the workout their coach expects of them.
    """
    repo = WorkoutScheduleRepository(get_supabase_client())
    existing = repo.get(user_id, schedule_id, athlete_id=athlete_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scheduled workout not found")
    _require_may_modify(user_id, athlete_id, existing, "scheduled workout")

    if not repo.delete(user_id, schedule_id, athlete_id=athlete_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scheduled workout not found")
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


@router.patch("/sessions/{session_id}", response_model=WorkoutSession)
async def update_session(
    session_id: UUID,
    body: WorkoutSessionUpdate,
    user_id: UUID = Depends(authenticate_request),
    athlete_id: UUID | None = Depends(acting_athlete),
) -> WorkoutSession:
    """Rename a logged session (SB-536).

    Same rule as deleting one: editable by whoever logged it, and by the coach
    for any of their athlete's. A name is a label on the record, so this never
    touches the sets — those are the record itself.
    """
    repo = WorkoutSessionsRepository(get_supabase_client())
    existing = repo.get(user_id, session_id, athlete_id=athlete_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    _require_may_modify(user_id, athlete_id, existing, "session")

    # exclude_unset, not exclude_none: clearing the name back to the default is
    # a legitimate edit, and indistinguishable from "not sent" otherwise.
    row = repo.update(
        user_id, session_id, body.model_dump(mode="json", exclude_unset=True), athlete_id=athlete_id
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    await invalidate_user(user_id)
    return WorkoutSession(**row)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    user_id: UUID = Depends(authenticate_request),
    athlete_id: UUID | None = Depends(acting_athlete),
) -> None:
    repo = WorkoutSessionsRepository(get_supabase_client())
    existing = repo.get(user_id, session_id, athlete_id=athlete_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    # A session is editable by whoever logged it, and by the coach for any of
    # their athlete's (SB-486) — so Gabe can fix his own typo without being able
    # to delete a session Matthew recorded.
    _require_may_modify(user_id, athlete_id, existing, "session")

    if not repo.delete(user_id, session_id, athlete_id=athlete_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    await invalidate_user(user_id)
