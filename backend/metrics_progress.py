"""Goal-progress computation — pure functions over entries + dates.

No DB or I/O here so it's trivially unit-testable. Given a goal, its metric's
aggregation rule, and the user's entries, compute progress for the goal's
current window. See docs/GOALS_TRACKING.md for the volume/frequency/streak model.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from src.shared.models.metric import (
    GoalComparator,
    GoalKind,
    GoalPeriod,
    GoalProgress,
    MetricAggregation,
    MetricEntry,
    MetricGoal,
    MetricType,
)

# App-wide local anchor (matches /stats, /metrics, and the cron jobs).
_LOCAL_TZ = ZoneInfo("America/New_York")


def _qualifying_days(entries: list[MetricEntry], goal: MetricGoal) -> set[date]:
    """Distinct days that count toward a frequency goal.

    Honors ``before_time`` — a day counts only if its entry started at/before that
    local clock time (e.g. "out the door by 8am"). An entry without a precise
    ``occurred_at`` can't satisfy a time goal, so it's excluded when one is set.
    """
    if goal.before_time is None:
        return {e.occurred_on for e in entries}
    days: set[date] = set()
    for e in entries:
        if e.occurred_at is None:
            continue
        if e.occurred_at.astimezone(_LOCAL_TZ).timetz().replace(tzinfo=None) <= goal.before_time:
            days.add(e.occurred_on)
    return days


def resolve_window(goal: MetricGoal, today: date) -> tuple[date, date]:
    """The [start, end] dates the goal is measured over, for a given 'today'."""
    if goal.period == GoalPeriod.year:
        return date(today.year, 1, 1), date(today.year, 12, 31)
    if goal.period == GoalPeriod.month:
        last = calendar.monthrange(today.year, today.month)[1]
        return date(today.year, today.month, 1), date(today.year, today.month, last)
    if goal.period == GoalPeriod.week:
        # ISO week: Monday start.
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    # custom — bounds are required by the model validator.
    assert goal.period_start is not None and goal.period_end is not None
    return goal.period_start, goal.period_end


def _aggregate(
    values: list[float], agg: MetricAggregation, entries_in_window: list[MetricEntry]
) -> float:
    if not values:
        return 0.0
    if agg == MetricAggregation.sum:
        return sum(values)
    if agg == MetricAggregation.max:
        return max(values)
    if agg == MetricAggregation.count:
        return float(len(values))
    # latest: value of the most recent entry (by occurred_at, then occurred_on).
    latest = max(
        entries_in_window,
        key=lambda e: (
            e.occurred_at.timestamp() if e.occurred_at else 0.0,
            e.occurred_on.toordinal(),
        ),
    )
    return float(latest.value)


def current_streak(entry_days: set[date], today: date, rest_budget: int) -> int:
    """Trailing run of days-with-an-entry ending at/near today.

    Tolerates up to ``rest_budget`` *consecutive* missed days before the chain
    is considered broken; a logged day resets the miss counter.
    """
    count = 0
    misses = 0
    day = today
    # Bound the walk so a corrupt date set can't loop forever.
    for _ in range(800):
        if day in entry_days:
            count += 1
            misses = 0
        else:
            misses += 1
            if misses > rest_budget:
                break
        day -= timedelta(days=1)
    return count


def compute_progress(
    goal: MetricGoal,
    metric: MetricType,
    entries: list[MetricEntry],
    today: date,
) -> GoalProgress:
    """Progress for ``goal`` given the user's ``entries`` for that metric."""
    window_start, window_end = resolve_window(goal, today)
    in_window = [e for e in entries if window_start <= e.occurred_on <= window_end]

    if goal.kind == GoalKind.volume:
        progress = _aggregate([e.value for e in in_window], metric.aggregation, in_window)
    elif goal.kind == GoalKind.frequency:
        # Count distinct qualifying days (honors before_time if set).
        progress = float(len(_qualifying_days(in_window, goal)))
    else:  # streak
        progress = float(current_streak({e.occurred_on for e in entries}, today, goal.rest_budget))

    percent = (progress / goal.target * 100.0) if goal.target else None
    met = (
        progress >= goal.target
        if goal.comparator == GoalComparator.gte
        else (0 < progress <= goal.target)
    )

    result = GoalProgress(
        goal=goal,
        window_start=window_start,
        window_end=window_end,
        progress=round(progress, 3),
        target=goal.target,
        percent=round(percent, 1) if percent is not None else None,
        met=met,
    )

    # Pace line — volume + reach-target only.
    if goal.kind == GoalKind.volume and goal.comparator == GoalComparator.gte:
        total_days = (window_end - window_start).days + 1
        elapsed = (min(today, window_end) - window_start).days + 1
        if 0 < elapsed <= total_days:
            expected = goal.target * (elapsed / total_days)
            result.on_pace = progress >= expected
            result.projected = round(progress / elapsed * total_days, 1)
            remaining_days = total_days - elapsed
            if remaining_days > 0:
                result.per_day_needed = round(max(0.0, goal.target - progress) / remaining_days, 3)
            else:
                result.per_day_needed = 0.0

    return result
