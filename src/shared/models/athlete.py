"""Coach platform foundation models (SB-195): roles, athletes, coach links."""

from __future__ import annotations

from datetime import datetime
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


class CoachAthlete(BaseModel):
    id: UUID
    coach_id: UUID
    athlete_id: UUID
    status: CoachAthleteStatus
    started_at: datetime
    ended_at: datetime | None = None
    created_at: datetime
