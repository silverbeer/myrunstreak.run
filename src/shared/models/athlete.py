"""Coach platform foundation models (SB-195): roles, athletes, coach links."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class Role(StrEnum):
    ADMIN = "admin"
    COACH = "coach"


class CoachAthleteStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"


class AthleteCreate(BaseModel):
    """Create a managed athlete (the coach owns it; no login needed)."""

    display_name: str = Field(min_length=1)
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    notes: str | None = None


class Athlete(BaseModel):
    id: UUID
    display_name: str
    birth_year: int | None = None
    linked_user_id: UUID | None = None
    created_by: UUID | None = None
    notes: str | None = None
    created_at: datetime
    profile: AthleteProfile | None = None


# Fields the linked athlete may edit on their own profile. The coach/admin may
# edit every profile field (incl. coaching_notes + sport/physical). Enforced
# server-side because the backend uses the service-role key (bypasses RLS).
ATHLETE_EDITABLE_FIELDS: frozenset[str] = frozenset(
    {
        "bio",
        "personal_goals",
        "athlete_email",
        "athlete_phone",
        "guardian_name",
        "guardian_email",
        "guardian_phone",
    }
)
# coaching_notes is coach-private: redacted from the linked-athlete read path.
COACH_PRIVATE_FIELDS: frozenset[str] = frozenset({"coaching_notes"})

# Fields that live on the core `athletes` row (not athlete_profiles). Coach-only.
ATHLETE_CORE_FIELDS: frozenset[str] = frozenset({"display_name", "birth_year"})


class AthleteProfile(BaseModel):
    """The 1:1 rich profile for an athlete (read model)."""

    sport: str | None = None
    position: str | None = None
    team: str | None = None
    dominant_side: str | None = None
    jersey_number: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    date_of_birth: date | None = None
    sex: str | None = None
    bio: str | None = None
    personal_goals: str | None = None
    athlete_email: str | None = None
    athlete_phone: str | None = None
    guardian_name: str | None = None
    guardian_email: str | None = None
    guardian_phone: str | None = None
    coaching_notes: str | None = None
    updated_at: datetime | None = None


class AthleteProfileUpdate(BaseModel):
    """Partial profile update. All optional; only set keys are applied, and the
    caller's role decides which keys are allowed (see ATHLETE_EDITABLE_FIELDS).

    display_name / birth_year live on the core `athletes` row (coach-only); the
    rest live on athlete_profiles. The route splits them on write."""

    model_config = {"extra": "forbid"}

    display_name: str | None = Field(default=None, min_length=1)
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    sport: str | None = None
    position: str | None = None
    team: str | None = None
    dominant_side: str | None = Field(default=None, pattern="^(left|right|both)$")
    jersey_number: str | None = None
    height_cm: float | None = Field(default=None, gt=0, le=300)
    weight_kg: float | None = Field(default=None, gt=0, le=500)
    date_of_birth: date | None = None
    sex: str | None = Field(default=None, pattern="^(male|female|other)$")
    bio: str | None = None
    personal_goals: str | None = None
    athlete_email: str | None = None
    athlete_phone: str | None = None
    guardian_name: str | None = None
    guardian_email: str | None = None
    guardian_phone: str | None = None
    coaching_notes: str | None = None


class CoachAthlete(BaseModel):
    id: UUID
    coach_id: UUID
    athlete_id: UUID
    status: CoachAthleteStatus
    started_at: datetime
    ended_at: datetime | None = None
    created_at: datetime
    # Resolved from the users table for display; the DB row carries only coach_id.
    coach_display_name: str | None = None
    coach_email: str | None = None


# Resolve the forward reference to AthleteProfile on Athlete.profile.
Athlete.model_rebuild()
