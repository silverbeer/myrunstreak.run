"""Coach home aggregate (SB-266) — everything a coach's landing page shows in
one response, so the SPA doesn't fan out N+1 calls per athlete."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.shared.models.athlete import Athlete


class CoachHomeAthlete(BaseModel):
    """An athlete card: who they are + where their training stands."""

    athlete: Athlete
    last_session_date: date | None = None
    sessions_count: int = 0
    latest_template_id: UUID | None = None
    latest_template_name: str | None = None
    latest_template_created_at: datetime | None = None
    #: A template was assigned and no session has been logged since ("Gabe
    #: hasn't logged Thursday yet"), or a template exists with no sessions ever.
    needs_attention: bool = False


class CoachHomeSession(BaseModel):
    """One row of the cross-athlete recent-activity feed."""

    id: UUID
    athlete_id: UUID
    athlete_name: str
    session_date: date
    type: str
    template_id: UUID | None = None
    template_name: str | None = None
    how_felt: str | None = None


class CoachHome(BaseModel):
    """Response of ``GET /coach/home``."""

    athletes: list[CoachHomeAthlete] = Field(default_factory=list)
    recent_sessions: list[CoachHomeSession] = Field(default_factory=list)
    #: Invites issued by the caller and not yet redeemed (admins only — empty
    #: for plain coaches, who cannot list invites).
    pending_invites: int = 0
