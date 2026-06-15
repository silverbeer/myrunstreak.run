"""The deterministic planning engine (SB-163).

``generate_plan`` is the entry point: given a goal set, the actuals logged so far,
known constraints, and today's readiness, it returns a :class:`PlanResult` — a
prescription per metric per day plus a feasibility verdict per goal.

Design notes:
  - **Per-metric prescriptions.** One run satisfies every running goal at once
    (the daily streak floor, the 4 long runs, the 135-mi total). So the engine
    collapses all goals on a metric into a *single* prescription per day via a
    precedence: constraint ``fixed`` > streak ``floor`` > long-run threshold >
    volume fill. ``PlanDay`` is keyed by (metric, day), not by goal.
  - **Training-aware for running** (long-run placement + weekly-ramp ceiling);
    **simple distributor** for everything else (push-ups, weigh-ins) — they have
    no injury-ramp concern.
  - **Done vs. prescribed.** Entries strictly before ``today`` are "done"; the
    plan prescribes ``[today .. period_end]``. A nightly recompute simply advances
    ``today``.

All distances are canonical km. Locked defaults (revisit per SB-167):
ramp +10%/wk, long runs on weekends, precedence as above, readiness affects the
flagged day only.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta

from src.shared.models.metric import GoalKind
from src.shared.models.planning import (
    ActualEntry,
    FeasibilityStatus,
    GoalPlanStatus,
    PlanConstraint,
    PlanDay,
    PlanDayKind,
    PlanningGoal,
    PlanResult,
    Readiness,
    ReadinessStatus,
)

# The one training-aware metric. Everything else uses the simple distributor.
RUNNING_KEY = "running_distance"

# Locked defaults (SB-167 revisits these with real usage data).
RAMP_PCT = 0.10  # max +10%/wk vs trailing average
DEFAULT_CEILING_KM = 16.09344  # ~10 mi — generous per-day cap when no history
TRAILING_DAYS = 28  # window for the recent-average ramp basis
MIN_LONG_SPACING_DAYS = 2  # qualifying long runs spaced >= this many days
_EPS = 1e-6


# --------------------------------------------------------------------------- #
# Small date / aggregation helpers
# --------------------------------------------------------------------------- #
def _daterange(start: date, end: date) -> list[date]:
    """Inclusive list of dates from ``start`` to ``end``."""
    if end < start:
        return []
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _is_weekend(day: date) -> bool:
    return day.weekday() >= 5  # Sat=5, Sun=6


def _daily_totals(entries: Sequence[ActualEntry], metric_key: str) -> dict[date, float]:
    """Sum entry values per day for one metric."""
    totals: dict[date, float] = defaultdict(float)
    for e in entries:
        if e.metric_key == metric_key:
            totals[e.occurred_on] += e.value
    return dict(totals)


def _spread(days: list[date], n: int) -> list[date]:
    """Pick ``n`` roughly evenly-spaced days from ``days`` (order preserved)."""
    if n <= 0 or not days:
        return []
    if n >= len(days):
        return list(days)
    step = len(days) / n
    return [days[min(len(days) - 1, int(i * step))] for i in range(n)]


def check_feasibility(remaining: float, capacity: float) -> FeasibilityStatus:
    """Core gate: is the remaining work reachable within the available capacity?"""
    if remaining > capacity + _EPS:
        return FeasibilityStatus.at_risk
    return FeasibilityStatus.on_track


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def generate_plan(
    *,
    period_start: date,
    period_end: date,
    today: date,
    goals: Sequence[PlanningGoal],
    entries: Sequence[ActualEntry],
    constraints: Sequence[PlanConstraint] = (),
    readiness: Sequence[Readiness] = (),
) -> PlanResult:
    """Build the full plan for ``[today .. period_end]`` from current reality."""
    plan_days: list[PlanDay] = []
    statuses: list[GoalPlanStatus] = []
    reasons: list[str] = []

    by_metric: dict[str, list[PlanningGoal]] = defaultdict(list)
    for g in goals:
        by_metric[g.metric_key].append(g)

    for metric_key, mgoals in by_metric.items():
        if metric_key == RUNNING_KEY:
            days, st = _plan_running(
                metric_key, mgoals, entries, constraints, readiness, today, period_end
            )
        else:
            days, st = _plan_simple(metric_key, mgoals, entries, today, period_end)
        plan_days.extend(days)
        statuses.extend(st)

    reasons = [s.detail for s in statuses if s.status is FeasibilityStatus.at_risk and s.detail]
    overall = (
        FeasibilityStatus.at_risk
        if any(s.status is FeasibilityStatus.at_risk for s in statuses)
        else FeasibilityStatus.on_track
    )

    return PlanResult(
        period_start=period_start,
        period_end=period_end,
        generated_for=today,
        days=sorted(plan_days, key=lambda d: (d.plan_on, d.metric_key)),
        goals=statuses,
        status=overall,
        at_risk_reasons=reasons,
    )


# ``recompute`` is the nightly/triggered path. For a pure engine it is identical
# to ``generate_plan`` with an advanced ``today`` — kept as a named alias so the
# API/cron layer (P1) reads intentionally.
recompute = generate_plan


# --------------------------------------------------------------------------- #
# Running: training-aware planner
# --------------------------------------------------------------------------- #
def _plan_running(
    metric_key: str,
    goals: Sequence[PlanningGoal],
    entries: Sequence[ActualEntry],
    constraints: Sequence[PlanConstraint],
    readiness: Sequence[Readiness],
    today: date,
    period_end: date,
) -> tuple[list[PlanDay], list[GoalPlanStatus]]:
    totals = _daily_totals(entries, metric_key)
    run_constraints = [c for c in constraints if c.metric_key == metric_key]
    readiness_by_day = {r.log_on: r.status for r in readiness}

    streak = next((g for g in goals if g.kind is GoalKind.streak), None)
    volume = next((g for g in goals if g.kind is GoalKind.volume), None)
    long_goal = next(
        (g for g in goals if g.kind is GoalKind.frequency and g.qualifier_threshold), None
    )

    floor_km: float = (streak.qualifier_threshold or 0.0) if streak else 0.0
    horizon = _daterange(today, period_end)

    # ---- classify each day: locked (constraint) vs free, apply readiness ----
    locked: dict[date, float] = {}
    free: list[date] = []
    rested: set[date] = set()
    for day in horizon:
        covering = next((c for c in run_constraints if c.covers(day)), None)
        if covering is not None and covering.pinned_value is not None:
            locked[day] = max(covering.pinned_value, 0.0)
            continue
        day_status = readiness_by_day.get(day, ReadinessStatus.good)
        if day_status is ReadinessStatus.sick:
            rested.add(day)  # rest day: only the streak floor, no long/extra
        free.append(day)

    # ---- progress so far (entries strictly before today) ----
    done_volume = sum(v for d, v in totals.items() if d < today)
    long_threshold: float = (long_goal.qualifier_threshold or 0.0) if long_goal else 0.0
    qualifying_done = (
        sum(1 for d, v in totals.items() if d < today and v >= long_threshold - _EPS)
        if long_goal
        else 0
    )

    # ---- weekly-ramp ceiling from recent history ----
    trailing_start = today - timedelta(days=TRAILING_DAYS)
    trailing = [v for d, v in totals.items() if trailing_start <= d < today]
    recent_avg = (sum(trailing) / TRAILING_DAYS) if trailing else 0.0
    recent_max = max(trailing, default=0.0)
    ceiling = max(DEFAULT_CEILING_KM, (1 + RAMP_PCT) * recent_avg, (1 + RAMP_PCT) * recent_max)

    # ---- place qualifying long runs on free, non-rest days ----
    needed_long = max(0, math.ceil(long_goal.target) - qualifying_done) if long_goal else 0
    eligible = [d for d in free if d not in rested]
    long_days = _place_long_runs(eligible, needed_long)

    # ---- base prescription per free day, then distribute remaining volume ----
    base: dict[date, float] = {}
    for day in free:
        if day in long_days:
            base[day] = max(floor_km, long_threshold)
        else:
            base[day] = floor_km

    planned_locked = sum(locked.values())
    prescribed: dict[date, float] = dict(base)
    volume_at_risk = False

    if volume is not None:
        remaining_volume = volume.target - done_volume - planned_locked
        base_total = sum(base.values())
        extra = remaining_volume - base_total
        if extra > _EPS:
            # Rest days (sick readiness) hold only the floor — no fill room, so
            # their displaced mileage flows to the other free days.
            room = {d: (0.0 if d in rested else max(0.0, ceiling - base[d])) for d in free}
            total_room = sum(room.values())
            capacity = base_total + total_room
            if remaining_volume > capacity + _EPS:
                volume_at_risk = True  # cannot fit even at the ceiling
            if total_room > _EPS:
                fillable = min(extra, total_room)
                for d in free:
                    prescribed[d] = base[d] + fillable * (room[d] / total_room)

    # ---- assemble PlanDay rows ----
    days_out: list[PlanDay] = []
    for day, val in locked.items():
        days_out.append(
            PlanDay(
                metric_key=metric_key, plan_on=day, prescribed_value=val, kind=PlanDayKind.fixed
            )
        )
    for day in free:
        if day in long_days:
            kind = PlanDayKind.long
        elif day in rested:
            kind = PlanDayKind.rest
        else:
            kind = PlanDayKind.easy
        days_out.append(
            PlanDay(
                metric_key=metric_key,
                plan_on=day,
                prescribed_value=round(prescribed[day], 3),
                kind=kind,
            )
        )

    # ---- per-goal status ----
    statuses: list[GoalPlanStatus] = []
    projected_total = done_volume + planned_locked + sum(prescribed.values())

    if streak is not None:
        # Every prescribed day clears the floor by construction (locked Chicago = 1 mi
        # = floor; free days default to floor; rest days keep the floor).
        below = [d for d in horizon if (prescribed.get(d, locked.get(d, 0.0)) + _EPS) < floor_km]
        statuses.append(
            GoalPlanStatus(
                metric_key=metric_key,
                kind=GoalKind.streak,
                target=streak.target,
                done=float(sum(1 for d in totals if d < today and totals[d] >= floor_km - _EPS)),
                remaining=float(len(horizon)),
                status=FeasibilityStatus.on_track if not below else FeasibilityStatus.at_risk,
                detail=None
                if not below
                else f"{len(below)} day(s) fall below the {floor_km:.2f}km floor",
            )
        )

    if long_goal is not None:
        projected_long = qualifying_done + len(long_days)
        ok = projected_long >= long_goal.target and long_threshold <= ceiling + _EPS
        statuses.append(
            GoalPlanStatus(
                metric_key=metric_key,
                kind=GoalKind.frequency,
                target=long_goal.target,
                done=float(qualifying_done),
                remaining=float(needed_long),
                projected=float(projected_long),
                status=FeasibilityStatus.on_track if ok else FeasibilityStatus.at_risk,
                detail=None
                if ok
                else f"can place only {len(long_days)} of {needed_long} long runs",
            )
        )

    if volume is not None:
        # Capacity = what locked days contribute + the most the free days can hold
        # at the ramp ceiling. ``check_feasibility`` is the gate; ``volume_at_risk``
        # is the same verdict captured during distribution.
        capacity = planned_locked + ceiling * len(free)
        vol_status = check_feasibility(volume.target - done_volume, capacity)
        if volume_at_risk:
            vol_status = FeasibilityStatus.at_risk
        statuses.append(
            GoalPlanStatus(
                metric_key=metric_key,
                kind=GoalKind.volume,
                target=volume.target,
                done=round(done_volume, 3),
                remaining=round(volume.target - done_volume, 3),
                projected=round(projected_total, 3),
                status=vol_status,
                detail=None
                if vol_status is FeasibilityStatus.on_track
                else f"projected {projected_total:.1f}km of {volume.target:.1f}km target",
            )
        )

    return days_out, statuses


def _place_long_runs(eligible: list[date], needed: int) -> set[date]:
    """Greedily place ``needed`` long runs: weekends first, spaced >= MIN_LONG_SPACING_DAYS."""
    if needed <= 0 or not eligible:
        return set()
    ordered = sorted(eligible, key=lambda d: (not _is_weekend(d), d))
    chosen: list[date] = []
    for day in ordered:
        if all(abs((day - c).days) >= MIN_LONG_SPACING_DAYS for c in chosen):
            chosen.append(day)
        if len(chosen) >= needed:
            break
    # If spacing was too tight to place enough, relax and fill from remaining days.
    if len(chosen) < needed:
        for day in sorted(eligible):
            if day not in chosen:
                chosen.append(day)
            if len(chosen) >= needed:
                break
    return set(chosen[:needed])


# --------------------------------------------------------------------------- #
# Non-running: simple distributor (no ramp, no long/rest cadence)
# --------------------------------------------------------------------------- #
def _plan_simple(
    metric_key: str,
    goals: Sequence[PlanningGoal],
    entries: Sequence[ActualEntry],
    today: date,
    period_end: date,
) -> tuple[list[PlanDay], list[GoalPlanStatus]]:
    totals = _daily_totals(entries, metric_key)
    horizon = _daterange(today, period_end)
    days_out: list[PlanDay] = []
    statuses: list[GoalPlanStatus] = []

    for goal in goals:
        if goal.kind is not GoalKind.frequency:
            # P0 only needs frequency for the non-running metrics (sessions, weigh-ins).
            continue
        threshold = goal.per_event_min if goal.per_event_min else _EPS
        done_count = sum(1 for d, v in totals.items() if d < today and v >= threshold - _EPS)
        needed = max(0, math.ceil(goal.target) - done_count)
        chosen = _spread(horizon, needed)
        value = goal.per_event_min if goal.per_event_min else 1.0
        for day in chosen:
            days_out.append(
                PlanDay(
                    metric_key=metric_key,
                    plan_on=day,
                    prescribed_value=value,
                    kind=PlanDayKind.easy,
                )
            )
        projected = done_count + len(chosen)
        ok = projected >= goal.target
        statuses.append(
            GoalPlanStatus(
                metric_key=metric_key,
                kind=GoalKind.frequency,
                target=goal.target,
                done=float(done_count),
                remaining=float(needed),
                projected=float(projected),
                status=FeasibilityStatus.on_track if ok else FeasibilityStatus.at_risk,
                detail=None if ok else f"only {len(horizon)} days left for {needed} more sessions",
            )
        )

    return days_out, statuses
