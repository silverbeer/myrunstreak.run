"""Authorization for privileged + relationship-scoped actions (SB-195).

Roles now live in the `user_roles` table. `require_admin` checks the DB role
first and still honors the legacy ADMIN_USER_IDS allowlist for one release, so
nothing breaks during the migration. Athlete access flows through the
coach<->athlete relationship.
"""

from __future__ import annotations

from uuid import UUID

from backend.config import get_settings
from fastapi import HTTPException, status
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import (
    AthletesRepository,
    CoachAthletesRepository,
    UserRolesRepository,
)

_FORBIDDEN = status.HTTP_403_FORBIDDEN


def _has_role(user_id: UUID, role: str) -> bool:
    return UserRolesRepository(get_supabase_client()).has_role(user_id, role)


def is_admin(user_id: UUID) -> bool:
    # DB role OR the legacy config allowlist (transitional).
    return _has_role(user_id, "admin") or str(user_id).lower() in get_settings().admin_ids()


def require_admin(user_id: UUID) -> None:
    """Raise 403 unless the user is an admin."""
    if not is_admin(user_id):
        raise HTTPException(status_code=_FORBIDDEN, detail="Admin privileges required")


def require_coach(user_id: UUID) -> None:
    """Raise 403 unless the user is a coach (admins are coaches too)."""
    if not (_has_role(user_id, "coach") or is_admin(user_id)):
        raise HTTPException(status_code=_FORBIDDEN, detail="Coach privileges required")


def can_access_athlete(user_id: UUID, athlete_id: UUID) -> bool:
    """True if the user is the athlete, actively coaches them, or is admin."""
    supabase = get_supabase_client()
    athlete = AthletesRepository(supabase).get(athlete_id)
    if athlete is None:
        return False
    if athlete.get("linked_user_id") and UUID(str(athlete["linked_user_id"])) == user_id:
        return True
    if CoachAthletesRepository(supabase).active_link_exists(user_id, athlete_id):
        return True
    return is_admin(user_id)


def require_athlete_access(user_id: UUID, athlete_id: UUID) -> None:
    """Raise 403 unless the user may act on this athlete."""
    if not can_access_athlete(user_id, athlete_id):
        raise HTTPException(status_code=_FORBIDDEN, detail="No access to this athlete")
