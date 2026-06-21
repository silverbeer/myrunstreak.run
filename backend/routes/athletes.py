"""/athletes — coach platform foundation (SB-195).

A coach creates managed athletes and manages the coach<->athlete roster.
Access to an athlete flows through an active coaching link (or being the
athlete, or admin) — enforced by can_access_athlete.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from backend.admin import is_admin, require_athlete_access, require_coach
from backend.auth import authenticate_request
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from src.shared.models import Athlete, AthleteCreate, CoachAthlete
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import (
    AthletesRepository,
    CoachAthletesRepository,
    UserRolesRepository,
)

router = APIRouter(prefix="/athletes", tags=["athletes"])
me_router = APIRouter(prefix="/me", tags=["me"])


class AssignCoachRequest(BaseModel):
    coach_id: UUID


@me_router.get("/roles")
def my_roles(user_id: UUID = Depends(authenticate_request)) -> dict[str, Any]:
    """The caller's platform roles."""
    roles = UserRolesRepository(get_supabase_client()).list_roles(user_id)
    return {"roles": sorted(roles), "is_admin": "admin" in roles}


@router.post("", response_model=Athlete, status_code=status.HTTP_201_CREATED)
def create_athlete(
    body: AthleteCreate,
    user_id: UUID = Depends(authenticate_request),
) -> Athlete:
    """Create a managed athlete and make the caller their (first) coach."""
    require_coach(user_id)
    supabase = get_supabase_client()
    row = AthletesRepository(supabase).create(
        created_by=user_id,
        display_name=body.display_name,
        birth_year=body.birth_year,
        notes=body.notes,
    )
    CoachAthletesRepository(supabase).assign(user_id, UUID(row["id"]))
    return Athlete(**row)


@router.get("", response_model=list[Athlete])
def list_athletes(
    user_id: UUID = Depends(authenticate_request),
) -> list[Athlete]:
    """Athletes the caller actively coaches."""
    rows = AthletesRepository(get_supabase_client()).list_for_coach(user_id)
    return [Athlete(**r) for r in rows]


@router.get("/{athlete_id}", response_model=Athlete)
def get_athlete(
    athlete_id: UUID,
    user_id: UUID = Depends(authenticate_request),
) -> Athlete:
    require_athlete_access(user_id, athlete_id)
    row = AthletesRepository(get_supabase_client()).get(athlete_id)
    assert row is not None  # require_athlete_access already proved existence + access
    return Athlete(**row)


@router.post(
    "/{athlete_id}/coaches", response_model=CoachAthlete, status_code=status.HTTP_201_CREATED
)
def assign_coach(
    athlete_id: UUID,
    body: AssignCoachRequest,
    user_id: UUID = Depends(authenticate_request),
) -> CoachAthlete:
    """Add a coach to an athlete. Caller must already have access; the new coach
    is granted the coach role so they can act on the athlete."""
    require_athlete_access(user_id, athlete_id)
    supabase = get_supabase_client()
    UserRolesRepository(supabase).grant(body.coach_id, "coach")
    link = CoachAthletesRepository(supabase).assign(body.coach_id, athlete_id)
    return CoachAthlete(**link)


@router.delete("/{athlete_id}/coaches/{coach_id}", status_code=status.HTTP_204_NO_CONTENT)
def end_coach(
    athlete_id: UUID,
    coach_id: UUID,
    user_id: UUID = Depends(authenticate_request),
) -> None:
    """End a coaching link. The coach themselves or an admin may do this."""
    if coach_id != user_id and not is_admin(user_id):
        require_athlete_access(user_id, athlete_id)  # else must have access
    CoachAthletesRepository(get_supabase_client()).end(coach_id, athlete_id)
