"""Generic metric tracking models — types catalog, entries, native goals.

Mirrors the schema in supabase/migrations/20260602120000_create_metric_tracking.sql.
Running is "metric #1"; weight, push-ups, etc. are just more metric types.
See docs/GOALS_TRACKING.md.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class MetricAggregation(str, Enum):
    """How a metric's entries roll up over a goal window."""

    sum = "sum"
    count = "count"
    latest = "latest"
    max = "max"


class GoalKind(str, Enum):
    volume = "volume"        # accumulate toward a target (sum to target)
    frequency = "frequency"  # do it N times in a window (count of qualifying days)
    streak = "streak"        # daily chain


class GoalPeriod(str, Enum):
    year = "year"
    month = "month"
    week = "week"
    custom = "custom"


class GoalComparator(str, Enum):
    gte = "gte"  # reach target (most goals)
    lte = "lte"  # stay under target (e.g. body weight)


class GoalStatus(str, Enum):
    active = "active"
    achieved = "achieved"
    archived = "archived"


class MetricType(BaseModel):
    """A row in the global metric catalog."""

    key: str
    display_name: str
    unit: str
    aggregation: MetricAggregation
    higher_is_better: bool = True


class MetricEntryCreate(BaseModel):
    """Input for logging an entry. ``occurred_on`` defaults to today server-side."""

    metric_key: str
    value: float = Field(ge=0, description="Canonical unit (km/kg/reps) or 1 for a check-in")
    occurred_on: date | None = None
    occurred_at: datetime | None = None
    note: str | None = Field(default=None, max_length=800)
    source: str = "manual"
    metadata: dict[str, Any] | None = None
    external_id: str | None = None


class MetricEntry(BaseModel):
    """A stored metric entry."""

    id: UUID
    user_id: UUID
    metric_key: str
    occurred_on: date
    occurred_at: datetime | None = None
    value: float
    note: str | None = None
    source: str = "manual"
    metadata: dict[str, Any] | None = None
    external_id: str | None = None
    created_at: datetime | None = None


class MetricGoalCreate(BaseModel):
    """Input for creating a native goal."""

    metric_key: str
    kind: GoalKind
    period: GoalPeriod
    target: float = Field(gt=0)
    comparator: GoalComparator = GoalComparator.gte
    rest_budget: int = Field(default=0, ge=0)
    period_start: date | None = None
    period_end: date | None = None
    qualifier_threshold: float | None = Field(default=None, ge=0)
    per_event_min: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _custom_needs_bounds(self) -> MetricGoalCreate:
        if self.period == GoalPeriod.custom:
            if self.period_start is None or self.period_end is None:
                raise ValueError("custom period requires period_start and period_end")
            if self.period_end < self.period_start:
                raise ValueError("period_end must be on or after period_start")
        return self


class MetricGoalUpdate(BaseModel):
    """Partial update — only provided fields change."""

    target: float | None = Field(default=None, gt=0)
    comparator: GoalComparator | None = None
    rest_budget: int | None = Field(default=None, ge=0)
    status: GoalStatus | None = None
    period_start: date | None = None
    period_end: date | None = None
    qualifier_threshold: float | None = Field(default=None, ge=0)
    per_event_min: float | None = Field(default=None, ge=0)


class MetricGoal(BaseModel):
    """A stored native goal."""

    id: UUID
    user_id: UUID
    metric_key: str
    kind: GoalKind
    period: GoalPeriod
    period_start: date | None = None
    period_end: date | None = None
    target: float
    comparator: GoalComparator = GoalComparator.gte
    rest_budget: int = 0
    status: GoalStatus = GoalStatus.active
    qualifier_threshold: float | None = None
    per_event_min: float | None = None
    created_at: datetime | None = None


class GoalProgress(BaseModel):
    """Computed progress for a goal over its current window.

    ``progress`` is the aggregated value (volume), count of qualifying days
    (frequency), or current chain length (streak). Pace fields are populated
    for volume goals only.
    """

    goal: MetricGoal
    window_start: date
    window_end: date
    progress: float
    target: float
    percent: float | None = None
    met: bool = False
    projected: float | None = None
    on_pace: bool | None = None
    per_day_needed: float | None = None
