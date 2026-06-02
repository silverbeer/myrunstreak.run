"""Unit tests for backend.metrics_progress — pure, no DB."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from backend.metrics_progress import compute_progress, current_streak, resolve_window
from src.shared.models.metric import (
    GoalComparator,
    GoalKind,
    GoalPeriod,
    MetricAggregation,
    MetricEntry,
    MetricGoal,
    MetricType,
)

USER = uuid4()


def _entry(metric_key: str, on: date, value: float, at: datetime | None = None) -> MetricEntry:
    return MetricEntry(
        id=uuid4(),
        user_id=USER,
        metric_key=metric_key,
        occurred_on=on,
        occurred_at=at,
        value=value,
    )


def _goal(**kw) -> MetricGoal:
    base = {
        "id": uuid4(),
        "user_id": USER,
        "metric_key": "pushups",
        "kind": GoalKind.volume,
        "period": GoalPeriod.month,
        "target": 100.0,
        "comparator": GoalComparator.gte,
        "rest_budget": 0,
    }
    base.update(kw)
    return MetricGoal(**base)


PUSHUPS = MetricType(key="pushups", display_name="Push-ups", unit="reps", aggregation=MetricAggregation.sum)
WEIGHT = MetricType(key="body_weight", display_name="Body weight", unit="kg", aggregation=MetricAggregation.latest, higher_is_better=False)


# ---- resolve_window ----

def test_window_year():
    s, e = resolve_window(_goal(period=GoalPeriod.year), date(2026, 6, 2))
    assert s == date(2026, 1, 1) and e == date(2026, 12, 31)


def test_window_month():
    s, e = resolve_window(_goal(period=GoalPeriod.month), date(2026, 2, 15))
    assert s == date(2026, 2, 1) and e == date(2026, 2, 28)  # 2026 not a leap year


def test_window_week_monday_start():
    # 2026-06-02 is a Tuesday → week is Mon 06-01 .. Sun 06-07.
    s, e = resolve_window(_goal(period=GoalPeriod.week), date(2026, 6, 2))
    assert s == date(2026, 6, 1) and e == date(2026, 6, 7)


def test_window_custom():
    g = _goal(period=GoalPeriod.custom, period_start=date(2026, 6, 1), period_end=date(2026, 6, 10))
    assert resolve_window(g, date(2026, 6, 5)) == (date(2026, 6, 1), date(2026, 6, 10))


# ---- volume ----

def test_volume_sum_and_pace():
    today = date(2026, 6, 10)  # day 10 of a 30-day month
    g = _goal(kind=GoalKind.volume, period=GoalPeriod.month, target=300.0)
    entries = [_entry("pushups", date(2026, 6, d), 10.0) for d in (1, 5, 10)]  # 30 total
    p = compute_progress(g, PUSHUPS, entries, today)
    assert p.progress == 30.0
    assert p.percent == 10.0
    assert p.met is False
    # 10/30 days elapsed; expected = 300*10/30 = 100; 30 < 100 → behind.
    assert p.on_pace is False
    assert p.projected == 90.0  # 30/10*30
    # remaining 20 days, need (300-30)/20 = 13.5/day
    assert p.per_day_needed == 13.5


def test_volume_met_when_target_reached():
    today = date(2026, 6, 30)
    g = _goal(kind=GoalKind.volume, period=GoalPeriod.month, target=100.0)
    entries = [_entry("pushups", date(2026, 6, 15), 120.0)]
    p = compute_progress(g, PUSHUPS, entries, today)
    assert p.progress == 120.0 and p.met is True


def test_volume_excludes_out_of_window_entries():
    today = date(2026, 6, 10)
    g = _goal(kind=GoalKind.volume, period=GoalPeriod.month, target=100.0)
    entries = [
        _entry("pushups", date(2026, 5, 31), 999.0),  # previous month — excluded
        _entry("pushups", date(2026, 6, 3), 25.0),
    ]
    p = compute_progress(g, PUSHUPS, entries, today)
    assert p.progress == 25.0


def test_weight_latest_lte_comparator():
    today = date(2026, 6, 20)
    g = _goal(metric_key="body_weight", kind=GoalKind.volume, period=GoalPeriod.month,
              target=80.0, comparator=GoalComparator.lte)
    entries = [
        _entry("body_weight", date(2026, 6, 1), 82.0, at=datetime(2026, 6, 1, tzinfo=UTC)),
        _entry("body_weight", date(2026, 6, 18), 79.5, at=datetime(2026, 6, 18, tzinfo=UTC)),
    ]
    p = compute_progress(g, WEIGHT, entries, today)
    assert p.progress == 79.5      # latest, not sum
    assert p.met is True           # 79.5 <= 80
    assert p.on_pace is None       # pace only for volume+gte


# ---- frequency ----

def test_frequency_counts_distinct_days():
    today = date(2026, 6, 3)  # week Mon 06-01..Sun 06-07
    g = _goal(metric_key="body_weight", kind=GoalKind.frequency, period=GoalPeriod.week, target=3.0)
    entries = [
        _entry("body_weight", date(2026, 6, 1), 80.0),
        _entry("body_weight", date(2026, 6, 1), 80.0),  # same day → still 1
        _entry("body_weight", date(2026, 6, 2), 80.0),
    ]
    p = compute_progress(g, WEIGHT, entries, today)
    assert p.progress == 2.0
    assert p.met is False


# ---- streak ----

def test_current_streak_basic_and_gap_breaks():
    today = date(2026, 6, 10)
    days = {date(2026, 6, 10), date(2026, 6, 9), date(2026, 6, 7)}  # gap on the 8th
    assert current_streak(days, today, rest_budget=0) == 2


def test_current_streak_rest_budget_tolerates_gap():
    today = date(2026, 6, 10)
    days = {date(2026, 6, 10), date(2026, 6, 8)}  # one missed day (the 9th)
    assert current_streak(days, today, rest_budget=1) == 2


def test_streak_goal_progress():
    today = date(2026, 6, 10)
    g = _goal(metric_key="running_distance", kind=GoalKind.streak, period=GoalPeriod.year, target=30.0, rest_budget=0)
    entries = [_entry("running_distance", date(2026, 6, d), 5.0) for d in (10, 9, 8)]
    rd = MetricType(key="running_distance", display_name="Running", unit="km", aggregation=MetricAggregation.sum)
    p = compute_progress(g, rd, entries, today)
    assert p.progress == 3.0
    assert p.met is False
