"""Goals-block presentation logic, shared between publish_status and /stats/goals.

The shape this module emits matches the GoalProgress interface that
qualityplaybook.dev's RunningStreak.vue expects, so the public status.json
and the dashboard's /stats/goals endpoint return structurally identical
goal payloads.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from src.shared.supabase_ops import GoalsRepository

KM_TO_MILES = 0.621371


def km_to_miles(km: float) -> float:
    return km * KM_TO_MILES


def render_goal(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert a goals-table row into the GoalProgress payload (miles).

    Returns None when the row is absent or its goal_km is null (the
    "no goal set on SmashRun" placeholder mark_absent writes).
    """
    if not row or row.get("goal_km") is None:
        return None
    goal_km = float(row["goal_km"])
    progress_km = float(row.get("progress_km") or 0.0)
    percent = (progress_km / goal_km * 100) if goal_km > 0 else None
    return {
        "goal_mi": round(km_to_miles(goal_km), 1),
        "progress_mi": round(km_to_miles(progress_km), 1),
        "percent": round(percent, 1) if percent is not None else None,
        "text": row.get("goal_text"),
        "fetched_at": row.get("fetched_at"),
    }


def build_goals_block(
    user_id: UUID,
    source_id: UUID | None,
    goals_repo: GoalsRepository,
    today: date,
) -> dict[str, Any]:
    """Yearly + monthly goal progress, in miles. Each is None when the user
    has no goal stored for the period (or no SmashRun source at all).
    """
    if source_id is None:
        return {"yearly": None, "monthly": None}

    yearly_row = goals_repo.get_by_period(user_id, source_id, today.year, None)
    monthly_row = goals_repo.get_by_period(user_id, source_id, today.year, today.month)
    return {"yearly": render_goal(yearly_row), "monthly": render_goal(monthly_row)}
