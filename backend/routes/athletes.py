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
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, model_validator
from src.shared.models import (
    ATHLETE_CORE_FIELDS,
    ATHLETE_EDITABLE_FIELDS,
    Athlete,
    AthleteCreate,
    AthleteProfile,
    AthleteProfileUpdate,
    CoachAthlete,
)
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import (
    AthletesRepository,
    CoachAthletesRepository,
    UserRolesRepository,
    UsersRepository,
)


def _is_coach_view(user_id: UUID, athlete_id: UUID) -> bool:
    """True if the caller edits/sees the athlete as a coach or admin (full
    access), vs. as the linked athlete themselves (subset + redaction)."""
    return is_admin(user_id) or CoachAthletesRepository(get_supabase_client()).active_link_exists(
        user_id, athlete_id
    )


def _athlete_with_profile(
    repo: AthletesRepository, row: dict[str, Any], *, coach_view: bool
) -> Athlete:
    """Attach the profile to an athlete row, redacting coach-private fields
    (coaching_notes) when the caller is the linked athlete, not a coach."""
    profile_row = repo.get_profile(UUID(row["id"]))
    profile = None
    if profile_row is not None:
        if not coach_view:
            profile_row = {**profile_row, "coaching_notes": None}
        profile = AthleteProfile(**profile_row)
    return Athlete(**row, profile=profile)


router = APIRouter(prefix="/athletes", tags=["athletes"])
me_router = APIRouter(prefix="/me", tags=["me"])


class AssignCoachRequest(BaseModel):
    """Assign a coach by user id or by email (one is required)."""

    coach_id: UUID | None = None
    coach_email: str | None = None

    @model_validator(mode="after")
    def _one_of(self) -> AssignCoachRequest:
        if not self.coach_id and not self.coach_email:
            raise ValueError("coach_id or coach_email is required")
        return self


@me_router.get("/roles")
def my_roles(user_id: UUID = Depends(authenticate_request)) -> dict[str, Any]:
    """The caller's platform roles."""
    roles = UserRolesRepository(get_supabase_client()).list_roles(user_id)
    return {"roles": sorted(roles), "is_admin": "admin" in roles}


@me_router.get("/athlete", response_model=Athlete | None)
def my_athlete(user_id: UUID = Depends(authenticate_request)) -> Athlete | None:
    """The athlete this user IS (via linked_user_id), with profile — or null.
    Lets the athlete UI load 'my profile' without knowing its athlete id."""
    repo = AthletesRepository(get_supabase_client())
    row = repo.get_by_linked_user(user_id)
    if row is None:
        return None
    # Linked-athlete view: coaching_notes redacted.
    return _athlete_with_profile(repo, row, coach_view=False)


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
    repo = AthletesRepository(get_supabase_client())
    row = repo.get(athlete_id)
    assert row is not None  # require_athlete_access already proved existence + access
    return _athlete_with_profile(repo, row, coach_view=_is_coach_view(user_id, athlete_id))


@router.patch("/{athlete_id}", response_model=Athlete)
def update_athlete_profile(
    athlete_id: UUID,
    body: AthleteProfileUpdate,
    user_id: UUID = Depends(authenticate_request),
) -> Athlete:
    """Patch an athlete's profile. Coach/admin may set any field; the linked
    athlete may set only ATHLETE_EDITABLE_FIELDS. Fails closed (403) on any
    disallowed key rather than silently dropping it."""
    require_athlete_access(user_id, athlete_id)
    coach_view = _is_coach_view(user_id, athlete_id)

    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    if not coach_view:
        disallowed = set(fields) - ATHLETE_EDITABLE_FIELDS
        if disallowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Not allowed to edit: {', '.join(sorted(disallowed))}",
            )

    repo = AthletesRepository(get_supabase_client())
    # display_name / birth_year live on the core athletes row; the rest on the
    # profile. Split so each lands in the right table.
    core = {k: fields.pop(k) for k in list(fields) if k in ATHLETE_CORE_FIELDS}
    if core:
        repo.update_core(athlete_id, core)
    if fields:
        repo.upsert_profile(athlete_id, fields, updated_by=user_id)
    row = repo.get(athlete_id)
    assert row is not None
    return _athlete_with_profile(repo, row, coach_view=coach_view)


@router.post(
    "/{athlete_id}/coaches", response_model=CoachAthlete, status_code=status.HTTP_201_CREATED
)
def assign_coach(
    athlete_id: UUID,
    body: AssignCoachRequest,
    user_id: UUID = Depends(authenticate_request),
) -> CoachAthlete:
    """Add a coach (by id or email) to an athlete. Caller must already have
    access; the new coach is granted the coach role so they can act."""
    require_athlete_access(user_id, athlete_id)
    supabase = get_supabase_client()

    coach_id = body.coach_id
    if coach_id is None:
        assert body.coach_email is not None
        found = UsersRepository(supabase).get_user_by_email(body.coach_email)
        if found is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "No user with that email — invite them first (stk invite create --role coach)",
            )
        coach_id = UUID(found["user_id"])

    UserRolesRepository(supabase).grant(coach_id, "coach")
    link = CoachAthletesRepository(supabase).assign(coach_id, athlete_id)
    return CoachAthlete(**link)


@router.get("/{athlete_id}/coaches", response_model=list[CoachAthlete])
def list_coaches(
    athlete_id: UUID,
    user_id: UUID = Depends(authenticate_request),
) -> list[CoachAthlete]:
    """Active coaches of an athlete, each enriched with the coach's name/email."""
    require_athlete_access(user_id, athlete_id)
    supabase = get_supabase_client()
    rows = CoachAthletesRepository(supabase).list_active_for_athlete(athlete_id)
    users = UsersRepository(supabase)
    # Resolve each coach's display name/email (the link row carries only the id).
    # Cache per coach_id so duplicate coaches don't re-query.
    resolved: dict[str, dict[str, Any] | None] = {}
    out: list[CoachAthlete] = []
    for r in rows:
        cid = r["coach_id"]
        if cid not in resolved:
            resolved[cid] = users.get_user_by_id(UUID(cid))
        user = resolved[cid]
        out.append(
            CoachAthlete(
                **r,
                coach_display_name=(user or {}).get("display_name"),
                coach_email=(user or {}).get("email"),
            )
        )
    return out


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
