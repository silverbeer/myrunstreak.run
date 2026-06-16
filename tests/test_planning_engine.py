"""Golden tests for the adaptive planning engine (SB-163).

The owner's real July scenario is the fixture:
  - run every day (streak, >= 1 mi/day)
  - 135 miles total (volume)
  - 4 runs > 5 mi (frequency, qualifier 5 mi)
  - push-ups >= 60, 10 times (frequency)
  - weigh in 10 times (frequency)
  - **Chicago Jul 12-16: run every day but capped at 1 mi**

Distances are canonical km; the scenario is authored in miles and converted.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.shared.models.metric import GoalKind
from src.shared.models.planning import (
    ActualEntry,
    FeasibilityStatus,
    PlanConstraint,
    PlanDayKind,
    PlanningGoal,
    Readiness,
    ReadinessStatus,
)
from src.shared.models.units import miles_to_km
from src.shared.planning import RUNNING_KEY, generate_plan

JUL_START = date(2026, 7, 1)
JUL_END = date(2026, 7, 31)
PUSHUPS = "pushups"
BODY_WEIGHT = "body_weight"  # stand-in metric for weigh-in frequency

MILE = miles_to_km(1.0)
FIVE_MI = miles_to_km(5.0)
TOTAL_MI = miles_to_km(135.0)


def _july_goals() -> list[PlanningGoal]:
    return [
        PlanningGoal(
            metric_key=RUNNING_KEY,
            kind=GoalKind.streak,
            target=31,
            period_start=JUL_START,
            period_end=JUL_END,
            qualifier_threshold=MILE,
        ),
        PlanningGoal(
            metric_key=RUNNING_KEY,
            kind=GoalKind.volume,
            target=TOTAL_MI,
            period_start=JUL_START,
            period_end=JUL_END,
        ),
        PlanningGoal(
            metric_key=RUNNING_KEY,
            kind=GoalKind.frequency,
            target=4,
            period_start=JUL_START,
            period_end=JUL_END,
            qualifier_threshold=FIVE_MI,
        ),
        PlanningGoal(
            metric_key=PUSHUPS,
            kind=GoalKind.frequency,
            target=10,
            period_start=JUL_START,
            period_end=JUL_END,
            per_event_min=60,
        ),
        PlanningGoal(
            metric_key=BODY_WEIGHT,
            kind=GoalKind.frequency,
            target=10,
            period_start=JUL_START,
            period_end=JUL_END,
        ),
    ]


def _chicago() -> PlanConstraint:
    return PlanConstraint(
        metric_key=RUNNING_KEY,
        start_on=date(2026, 7, 12),
        end_on=date(2026, 7, 16),
        cap=MILE,
        floor=MILE,
        reason="Chicago travel",
    )


def _plan_fresh(**kwargs):
    """A start-of-month plan (today=Jul 1, no actuals yet)."""
    defaults = {
        "period_start": JUL_START,
        "period_end": JUL_END,
        "today": JUL_START,
        "goals": _july_goals(),
        "entries": [],
        "constraints": [_chicago()],
    }
    defaults.update(kwargs)
    return generate_plan(**defaults)


# --------------------------------------------------------------------------- #
# Constraints: Chicago days are pinned at 1 mi and locked
# --------------------------------------------------------------------------- #
def test_chicago_days_pinned_at_one_mile():
    result = _plan_fresh()
    run_days = {d.plan_on: d for d in result.days_for(RUNNING_KEY)}

    for day in (
        date(2026, 7, 12),
        date(2026, 7, 13),
        date(2026, 7, 14),
        date(2026, 7, 15),
        date(2026, 7, 16),
    ):
        d = run_days[day]
        assert d.kind is PlanDayKind.fixed
        assert d.prescribed_value == pytest.approx(MILE, abs=1e-3)


def test_streak_floor_every_single_day():
    result = _plan_fresh()
    run_days = result.days_for(RUNNING_KEY)
    # Every day of July has a running prescription >= the 1-mile floor.
    assert len(run_days) == 31
    assert all(d.prescribed_value >= MILE - 1e-3 for d in run_days)


# --------------------------------------------------------------------------- #
# Volume: the 5-mile Chicago shortfall is absorbed into the other 26 days
# --------------------------------------------------------------------------- #
def test_volume_target_met_and_shortfall_absorbed():
    result = _plan_fresh()
    run_days = result.days_for(RUNNING_KEY)
    planned_total = sum(d.prescribed_value for d in run_days)

    # The whole 135-mi target is planned across the month...
    assert planned_total == pytest.approx(TOTAL_MI, abs=0.5)

    # ...and the non-Chicago days carry the load: Chicago contributes only 5 mi,
    # so the other 26 days must cover 130.
    chicago = {date(2026, 7, d) for d in range(12, 17)}
    free_total = sum(d.prescribed_value for d in run_days if d.plan_on not in chicago)
    assert free_total == pytest.approx(TOTAL_MI - 5 * MILE, abs=0.5)

    vol = next(g for g in result.goals if g.kind is GoalKind.volume)
    assert vol.status is FeasibilityStatus.on_track


# --------------------------------------------------------------------------- #
# Long runs: 4 placed, none on a capped Chicago day, spaced apart
# --------------------------------------------------------------------------- #
def test_four_long_runs_placed_off_capped_days():
    result = _plan_fresh()
    long_days = [d for d in result.days_for(RUNNING_KEY) if d.kind is PlanDayKind.long]
    assert len(long_days) == 4

    chicago = {date(2026, 7, d) for d in range(12, 17)}
    for d in long_days:
        assert d.plan_on not in chicago
        assert d.prescribed_value >= FIVE_MI - 1e-3

    # Spaced >= 2 days apart.
    dates = sorted(d.plan_on for d in long_days)
    assert all((b - a).days >= 2 for a, b in zip(dates, dates[1:], strict=False))

    freq = next(
        g for g in result.goals if g.kind is GoalKind.frequency and g.metric_key == RUNNING_KEY
    )
    assert freq.status is FeasibilityStatus.on_track


# --------------------------------------------------------------------------- #
# Non-running metrics: simple distributor places the right number of sessions
# --------------------------------------------------------------------------- #
def test_pushups_and_weighins_scheduled():
    result = _plan_fresh()

    pushups = result.days_for(PUSHUPS)
    assert len(pushups) == 10
    assert all(d.prescribed_value == 60 for d in pushups)

    weighins = result.days_for(BODY_WEIGHT)
    assert len(weighins) == 10
    assert all(d.prescribed_value == 1 for d in weighins)

    assert result.status is FeasibilityStatus.on_track


# --------------------------------------------------------------------------- #
# Feasibility gate: flips AT_RISK when the goal can't be reached
# --------------------------------------------------------------------------- #
def test_gate_flags_at_risk_when_behind_and_infeasible():
    # Jul 28: only 80 mi done, 55 mi left over 4 days — impossible under the ramp
    # ceiling (~10 mi/day → ~40 mi capacity).
    done = [
        ActualEntry(
            metric_key=RUNNING_KEY, occurred_on=date(2026, 7, d), value=miles_to_km(80 / 27)
        )
        for d in range(1, 28)
    ]
    result = generate_plan(
        period_start=JUL_START,
        period_end=JUL_END,
        today=date(2026, 7, 28),
        goals=_july_goals(),
        entries=done,
        constraints=[],
    )
    vol = next(g for g in result.goals if g.kind is GoalKind.volume)
    assert vol.status is FeasibilityStatus.at_risk
    assert result.status is FeasibilityStatus.at_risk
    assert result.at_risk_reasons


def test_on_track_when_ahead_of_pace():
    # Halfway through with more than half the miles banked → never at risk.
    done = [
        ActualEntry(metric_key=RUNNING_KEY, occurred_on=date(2026, 7, d), value=miles_to_km(5.0))
        for d in range(1, 16)
    ]
    result = generate_plan(
        period_start=JUL_START,
        period_end=JUL_END,
        today=date(2026, 7, 16),
        goals=[_july_goals()[1]],  # volume only
        entries=done,
        constraints=[],
    )
    vol = next(g for g in result.goals if g.kind is GoalKind.volume)
    assert vol.status is FeasibilityStatus.on_track


# --------------------------------------------------------------------------- #
# Regression: prior-month runs (pulled only for the ramp ceiling) must NOT
# count as this month's progress. Caught in live e2e — June runs were inflating
# July's "done" and shrinking the plan. today=Jul 1 with a full June of entries.
# --------------------------------------------------------------------------- #
def test_prior_month_entries_do_not_count_as_done():
    june_runs = [
        ActualEntry(metric_key=RUNNING_KEY, occurred_on=date(2026, 6, d), value=miles_to_km(6.0))
        for d in range(1, 31)  # 30 June days, 6 mi each, several over the 5-mi long-run bar
    ]
    result = generate_plan(
        period_start=JUL_START,
        period_end=JUL_END,
        today=JUL_START,  # plan all of July; nothing done IN July yet
        goals=_july_goals(),
        entries=june_runs,
        constraints=[_chicago()],
    )
    vol = next(g for g in result.goals if g.kind is GoalKind.volume)
    assert vol.done == pytest.approx(0.0, abs=1e-6)  # June must not leak in
    # The full target is still planned across July, not just a remainder.
    planned = sum(d.prescribed_value for d in result.days_for(RUNNING_KEY))
    assert planned == pytest.approx(TOTAL_MI, abs=0.5)
    # And all 4 long runs are placed (no June run miscounted as a done long run).
    assert sum(1 for d in result.days_for(RUNNING_KEY) if d.kind is PlanDayKind.long) == 4


# --------------------------------------------------------------------------- #
# Readiness: a sick day becomes rest but keeps the streak floor
# --------------------------------------------------------------------------- #
def test_sick_day_is_rest_but_keeps_streak_floor():
    sick_day = date(2026, 7, 3)
    result = _plan_fresh(readiness=[Readiness(log_on=sick_day, status=ReadinessStatus.sick)])
    day = next(d for d in result.days_for(RUNNING_KEY) if d.plan_on == sick_day)
    assert day.kind is PlanDayKind.rest
    assert day.prescribed_value == pytest.approx(MILE, abs=1e-3)
    # The streak survives, and the displaced mileage is still planned elsewhere.
    assert result.status is FeasibilityStatus.on_track
    planned_total = sum(d.prescribed_value for d in result.days_for(RUNNING_KEY))
    assert planned_total == pytest.approx(TOTAL_MI, abs=0.5)
