"""Adaptive monthly planning — domain models (SB-163).

Pure-data models the planner consumes and produces. **No I/O.** The engine in
``src/shared/planning/`` is a pure function over these; the repository/backend
layer (P1, SB-164) maps Supabase rows to/from them.

All distances are canonical **kilometers** (like ``runs.distance_km`` and
``metric_entries.value``); convert to miles at the presentation edge.

Design: planning reuses ``metric_goals`` as the target model — a stored goal maps
to a :class:`PlanningGoal`. The qualifier fields (``qualifier_threshold``,
``per_event_min``) are an additive Phase-1 concern on ``metric_goals``; the engine
just needs them as input and stays decoupled from schema evolution.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from .metric import GoalKind


class ReadinessStatus(StrEnum):
    """How the user feels on a given day. Absence of a row == ``good``."""

    good = "good"
    tired = "tired"  # down-shift today to an easy day
    sick = "sick"  # today becomes rest (streak floor still honored)


class PlanDayKind(StrEnum):
    """Training role of a prescribed day."""

    long = "long"  # a qualifying long run
    easy = "easy"  # ordinary distributed day
    rest = "rest"  # recovery (streak floor still prescribed if a streak goal exists)
    fixed = "fixed"  # constraint-locked (e.g. travel cap)


class FeasibilityStatus(StrEnum):
    """The planner's verdict on whether a goal is still reachable."""

    on_track = "on_track"
    at_risk = "at_risk"


class ActualEntry(BaseModel):
    """A logged metric event the planner reads (the subset of ``MetricEntry`` it needs)."""

    metric_key: str
    occurred_on: date
    value: float = Field(ge=0, description="Canonical unit (km/reps) or 1 for a check-in")


class PlanConstraint(BaseModel):
    """A known-in-advance limit on a metric over a date range.

    ``cap`` = max prescribable/day, ``floor`` = min still required/day. Both set =
    a pinned value (Chicago: cap=floor=1 mi). Distances in canonical km.
    """

    metric_key: str
    start_on: date
    end_on: date
    cap: float | None = Field(default=None, ge=0)
    floor: float | None = Field(default=None, ge=0)
    reason: str | None = None

    @model_validator(mode="after")
    def _check_bounds(self) -> PlanConstraint:
        if self.end_on < self.start_on:
            raise ValueError("end_on must be on or after start_on")
        if self.cap is not None and self.floor is not None and self.floor > self.cap:
            raise ValueError("floor must be <= cap")
        return self

    def covers(self, day: date) -> bool:
        return self.start_on <= day <= self.end_on

    @property
    def pinned_value(self) -> float | None:
        """The value a covered day is locked to: cap if set, else floor."""
        return self.cap if self.cap is not None else self.floor


class Readiness(BaseModel):
    """A daily "how I feel" signal."""

    log_on: date
    status: ReadinessStatus = ReadinessStatus.good
    note: str | None = None


class PlanningGoal(BaseModel):
    """Engine input: one monthly target. Maps from a stored ``metric_goals`` row.

    ``qualifier_threshold`` does double duty:
      - ``streak`` goal → the daily floor (run >= 1 mi/day).
      - ``frequency`` goal → the per-day threshold a day must clear to count
        (a run >= 5 mi qualifies as one of the "4 long runs").

    ``per_event_min`` is the minimum value each qualifying event needs (push-ups
    >= 60 per session).
    """

    metric_key: str
    kind: GoalKind
    target: float = Field(gt=0)
    period_start: date
    period_end: date
    qualifier_threshold: float | None = Field(default=None, ge=0)
    per_event_min: float | None = Field(default=None, ge=0)
    rest_budget: int = Field(default=0, ge=0)


class PlanDay(BaseModel):
    """A generated prescription for one metric on one day (the cache row)."""

    metric_key: str
    plan_on: date
    prescribed_value: float = Field(ge=0)
    kind: PlanDayKind


class GoalPlanStatus(BaseModel):
    """Per-goal progress + verdict for a recompute."""

    metric_key: str
    kind: GoalKind
    target: float
    done: float
    remaining: float
    projected: float | None = None
    status: FeasibilityStatus
    detail: str | None = None  # catch-up note, or why it is at risk


class PlanResult(BaseModel):
    """The full output of a recompute — the planner's complete answer.

    ``days`` holds every prescription for ``[generated_for .. period_end]``;
    ``goals`` holds per-goal status; ``status`` is the month-level roll-up
    (at_risk if any goal is at risk).
    """

    period_start: date
    period_end: date
    generated_for: date  # the "today" the recompute was run for
    days: list[PlanDay]
    goals: list[GoalPlanStatus]
    status: FeasibilityStatus
    at_risk_reasons: list[str] = Field(default_factory=list)

    def days_for(self, metric_key: str) -> list[PlanDay]:
        """Prescriptions for one metric, in date order."""
        return sorted(
            (d for d in self.days if d.metric_key == metric_key),
            key=lambda d: d.plan_on,
        )
