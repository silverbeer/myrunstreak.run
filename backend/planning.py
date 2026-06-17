"""Plan assembly service (SB-164).

Glue between Supabase and the pure planning engine (``src/shared/planning/``):
gather a user's goals + actuals + constraints + readiness for a month, map them
into engine inputs, run the engine, and persist the resulting prescriptions.

The engine owns all the math; this module only does I/O + mapping. The plan is a
derived cache — ``build_plan`` recomputes it from scratch every call.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from src.shared.models.metric import GoalKind
from src.shared.models.planning import (
    ActualEntry,
    PlanConstraint,
    PlanningGoal,
    PlanResult,
    Readiness,
    ReadinessStatus,
)
from src.shared.planning import generate_plan
from src.shared.supabase_ops import (
    MetricEntriesRepository,
    MetricGoalsRepository,
    PlanConstraintsRepository,
    PlanDaysRepository,
    ReadinessRepository,
)
from supabase import Client

# Trailing history the ramp ceiling needs, beyond the period itself.
_TRAILING_DAYS = 28
_PERIOD_RE = re.compile(r"^(\d{4})-(\d{2})$")


def period_bounds(period: str) -> tuple[date, date]:
    """Parse a ``YYYY-MM`` period into inclusive (first_day, last_day)."""
    m = _PERIOD_RE.match(period)
    if not m:
        raise ValueError(f"period must be 'YYYY-MM', got '{period}'")
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        raise ValueError(f"month out of range in period '{period}'")
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def period_for(day: date) -> str:
    """The ``YYYY-MM`` period a date falls in."""
    return f"{day.year:04d}-{day.month:02d}"


def to_planning_goal(row: dict[str, Any], period_start: date, period_end: date) -> PlanningGoal:
    """Map a stored ``metric_goals`` row onto the engine's monthly target."""
    return PlanningGoal(
        metric_key=row["metric_key"],
        kind=GoalKind(row["kind"]),
        target=float(row["target"]),
        period_start=period_start,
        period_end=period_end,
        qualifier_threshold=(
            float(row["qualifier_threshold"])
            if row.get("qualifier_threshold") is not None
            else None
        ),
        per_event_min=(
            float(row["per_event_min"]) if row.get("per_event_min") is not None else None
        ),
        rest_budget=int(row.get("rest_budget") or 0),
    )


def _is_plan_goal(row: dict[str, Any]) -> bool:
    """Monthly-planning goals only.

    Excludes:
      - yearly goals (the SmashRun mirror's cadence, not a month's daily plan),
      - weekly goals (the monthly planner doesn't schedule a weekly cadence),
      - time-of-day goals (``before_time`` — a habit tracked + coached via the
        goals/progress engine; it doesn't change what distance to run).
    """
    if row.get("period") in ("year", "week"):
        return False
    if row.get("before_time") is not None:
        return False
    return True


def build_plan(
    supabase: Client,
    user_id: UUID,
    period: str,
    today: date,
) -> PlanResult:
    """Recompute a user's plan for ``period`` from current reality (no persistence)."""
    period_start, period_end = period_bounds(period)
    # Where the plan starts prescribing: today, clamped into the period. A future
    # month plans from its first day; a current month plans from today.
    plan_today = min(max(today, period_start), period_end)

    goal_rows = MetricGoalsRepository(supabase).list(user_id, status="active")
    goals = [to_planning_goal(r, period_start, period_end) for r in goal_rows if _is_plan_goal(r)]

    history_from = period_start - timedelta(days=_TRAILING_DAYS)
    entry_rows = MetricEntriesRepository(supabase).list(
        user_id, date_from=history_from, date_to=period_end, limit=2000
    )
    entries = [
        ActualEntry(
            metric_key=r["metric_key"],
            occurred_on=date.fromisoformat(r["occurred_on"]),
            value=float(r["value"]),
        )
        for r in entry_rows
    ]

    constraint_rows = PlanConstraintsRepository(supabase).list(
        user_id, date_from=period_start, date_to=period_end
    )
    constraints = [
        PlanConstraint(
            metric_key=r["metric_key"],
            start_on=date.fromisoformat(r["start_on"]),
            end_on=date.fromisoformat(r["end_on"]),
            cap=float(r["cap"]) if r.get("cap") is not None else None,
            floor=float(r["floor"]) if r.get("floor") is not None else None,
            reason=r.get("reason"),
        )
        for r in constraint_rows
    ]

    readiness_rows = ReadinessRepository(supabase).list(
        user_id, date_from=period_start, date_to=period_end
    )
    readiness = [
        Readiness(
            log_on=date.fromisoformat(r["log_on"]),
            status=ReadinessStatus(r["status"]),
            note=r.get("note"),
        )
        for r in readiness_rows
    ]

    return generate_plan(
        period_start=period_start,
        period_end=period_end,
        today=plan_today,
        goals=goals,
        entries=entries,
        constraints=constraints,
        readiness=readiness,
    )


def build_and_store_plan(
    supabase: Client,
    user_id: UUID,
    period: str,
    today: date,
) -> PlanResult:
    """Recompute and persist the plan: delete-future + reinsert ``plan_days``."""
    result = build_plan(supabase, user_id, period, today)
    rows = [
        {
            "metric_key": d.metric_key,
            "plan_on": d.plan_on.isoformat(),
            "prescribed_value": d.prescribed_value,
            "kind": d.kind.value,
        }
        for d in result.days
    ]
    PlanDaysRepository(supabase).replace_from(user_id, result.generated_for, rows)
    return result
