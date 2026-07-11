"""/coach — the coach's home aggregate (SB-266).

One response powers the coach landing page: athlete cards with training state,
a cross-athlete recent-activity feed, and the pending-invite count. Aggregated
server-side so the SPA doesn't fan out a call per athlete.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from backend.admin import is_admin, require_coach
from backend.auth import authenticate_request
from fastapi import APIRouter, Depends
from src.shared.models import Athlete
from src.shared.models.coach_home import CoachHome, CoachHomeAthlete, CoachHomeSession
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import (
    AthletesRepository,
    InvitesRepository,
    WorkoutSessionsRepository,
    WorkoutTemplatesRepository,
)

router = APIRouter(prefix="/coach", tags=["coach"])

#: Sessions pulled for the aggregate — enough to compute per-athlete state at
#: this product's scale; the feed itself shows only the newest few.
_SESSION_WINDOW = 200
_FEED_LIMIT = 10


@router.get("/home", response_model=CoachHome)
def coach_home(user_id: UUID = Depends(authenticate_request)) -> CoachHome:
    """Everything the coach landing page needs, in one call."""
    require_coach(user_id)
    supabase = get_supabase_client()

    athletes = [Athlete(**r) for r in AthletesRepository(supabase).list_for_coach(user_id)]
    ids = [a.id for a in athletes]
    names = {str(a.id): a.display_name for a in athletes}

    sessions = WorkoutSessionsRepository(supabase).list_for_athletes(ids, limit=_SESSION_WINDOW)
    templates = WorkoutTemplatesRepository(supabase).list_for_athletes(ids)
    template_names = {t["id"]: t["name"] for t in templates}

    # Both lists arrive newest-first, so "first seen per athlete" == latest.
    last_session: dict[str, str] = {}
    session_counts: dict[str, int] = {}
    for s in sessions:
        aid = s["athlete_id"]
        last_session.setdefault(aid, s["session_date"])
        session_counts[aid] = session_counts.get(aid, 0) + 1
    latest_template: dict[str, dict] = {}
    for t in templates:
        latest_template.setdefault(t["athlete_id"], t)

    cards: list[CoachHomeAthlete] = []
    for athlete in athletes:
        aid = str(athlete.id)
        tpl = latest_template.get(aid)
        last = last_session.get(aid)
        needs_attention = False
        if tpl is not None:
            assigned = datetime.fromisoformat(tpl["created_at"]).astimezone(UTC).date()
            # Assigned a plan and nothing logged since (or nothing logged ever).
            needs_attention = last is None or datetime.fromisoformat(last).date() < assigned
        cards.append(
            CoachHomeAthlete(
                athlete=athlete,
                last_session_date=last,  # type: ignore[arg-type]  # ISO date str -> date via pydantic
                sessions_count=session_counts.get(aid, 0),
                latest_template_id=tpl["id"] if tpl else None,
                latest_template_name=tpl["name"] if tpl else None,
                latest_template_created_at=tpl["created_at"] if tpl else None,
                needs_attention=needs_attention,
            )
        )
    # Athletes needing attention float to the top.
    cards.sort(key=lambda c: (not c.needs_attention, c.athlete.display_name.lower()))

    feed = [
        CoachHomeSession(
            id=s["id"],
            athlete_id=s["athlete_id"],
            athlete_name=names.get(s["athlete_id"], "?"),
            session_date=s["session_date"],
            type=s["type"],
            template_id=s.get("template_id"),
            template_name=template_names.get(s.get("template_id") or ""),
            how_felt=s.get("how_felt"),
        )
        for s in sessions[:_FEED_LIMIT]
    ]

    pending = 0
    if is_admin(user_id):
        now = datetime.now(UTC)
        pending = sum(
            1
            for i in InvitesRepository(supabase).list_by_creator(user_id)
            if i.get("redeemed_at") is None and datetime.fromisoformat(i["expires_at"]) > now
        )

    return CoachHome(athletes=cards, recent_sessions=feed, pending_invites=pending)
