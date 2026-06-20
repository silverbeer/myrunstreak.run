"""Tests for the backend plan-assembly service (SB-164).

Covers the Supabase<->engine glue: period parsing, goal mapping, and a full
build/persist round-trip driven through a fake Supabase client (no live DB).
The engine's own behavior is covered in test_planning_engine.py.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from backend.planning import (
    build_and_store_plan,
    build_plan,
    period_bounds,
    period_for,
    to_planning_goal,
)
from src.shared.models.metric import GoalKind
from src.shared.models.planning import FeasibilityStatus, PlanDayKind

MILE = 1.609344
FIVE_MI = 5 * MILE
TOTAL = 135 * MILE


# --------------------------------------------------------------------------- #
# Fake Supabase — chainable query builder returning canned rows per table
# --------------------------------------------------------------------------- #
class _FakeQuery:
    def __init__(self, table: str, store: dict, captured: dict):
        self.table = table
        self.store = store
        self.captured = captured
        self._mode = "select"
        self._payload: Any = None

    def select(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def eq(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def gte(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def lte(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def order(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def limit(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def range(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def insert(self, payload: Any) -> _FakeQuery:
        self._mode, self._payload = "insert", payload
        return self

    def upsert(self, payload: Any, **k: Any) -> _FakeQuery:
        self._mode, self._payload = "upsert", payload
        return self

    def delete(self) -> _FakeQuery:
        self._mode = "delete"
        return self

    def execute(self) -> SimpleNamespace:
        if self._mode in ("insert", "upsert"):
            rows = self._payload if isinstance(self._payload, list) else [self._payload]
            self.captured.setdefault(self.table, []).extend(rows)
            return SimpleNamespace(data=rows)
        if self._mode == "delete":
            self.captured.setdefault(f"{self.table}:deleted", []).append(True)
            return SimpleNamespace(data=[])
        return SimpleNamespace(data=list(self.store.get(self.table, [])))


class _FakeSupabase:
    def __init__(self, store: dict):
        self.store = store
        self.captured: dict = {}

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(name, self.store, self.captured)


def _july_store() -> dict:
    return {
        "metric_goals": [
            {
                "metric_key": "running_distance",
                "kind": "streak",
                "target": 31,
                "period": "month",
                "qualifier_threshold": MILE,
                "per_event_min": None,
                "rest_budget": 0,
            },
            {
                "metric_key": "running_distance",
                "kind": "volume",
                "target": TOTAL,
                "period": "month",
                "qualifier_threshold": None,
                "per_event_min": None,
                "rest_budget": 0,
            },
            {
                "metric_key": "running_distance",
                "kind": "frequency",
                "target": 4,
                "period": "month",
                "qualifier_threshold": FIVE_MI,
                "per_event_min": None,
                "rest_budget": 0,
            },
            {
                "metric_key": "pushups",
                "kind": "frequency",
                "target": 10,
                "period": "month",
                "qualifier_threshold": None,
                "per_event_min": 60,
                "rest_budget": 0,
            },
            {
                "metric_key": "body_weight",
                "kind": "frequency",
                "target": 10,
                "period": "month",
                "qualifier_threshold": None,
                "per_event_min": None,
                "rest_budget": 0,
            },
        ],
        "metric_entries": [],
        "plan_constraints": [
            {
                "metric_key": "running_distance",
                "start_on": "2026-07-12",
                "end_on": "2026-07-16",
                "cap": MILE,
                "floor": MILE,
                "reason": "Chicago travel",
            },
        ],
        "readiness_log": [],
    }


# --------------------------------------------------------------------------- #
# Pure mapping
# --------------------------------------------------------------------------- #
def test_period_bounds_and_for():
    assert period_bounds("2026-07") == (date(2026, 7, 1), date(2026, 7, 31))
    assert period_bounds("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
    assert period_for(date(2026, 7, 9)) == "2026-07"


def test_period_bounds_rejects_garbage():
    with pytest.raises(ValueError):
        period_bounds("2026/07")
    with pytest.raises(ValueError):
        period_bounds("2026-13")


def test_to_planning_goal_maps_qualifiers():
    row = {
        "metric_key": "running_distance",
        "kind": "frequency",
        "target": 4,
        "qualifier_threshold": FIVE_MI,
        "per_event_min": None,
        "rest_budget": 0,
    }
    g = to_planning_goal(row, date(2026, 7, 1), date(2026, 7, 31))
    assert g.kind is GoalKind.frequency
    assert g.target == 4
    assert g.qualifier_threshold == pytest.approx(FIVE_MI)
    assert g.period_end == date(2026, 7, 31)


# --------------------------------------------------------------------------- #
# Full build through the fake client (future month plans from day 1)
# --------------------------------------------------------------------------- #
def test_build_plan_july_end_to_end():
    supa = _FakeSupabase(_july_store())
    result = build_plan(supa, uuid4(), "2026-07", today=date(2026, 6, 15))

    assert result.generated_for == date(2026, 7, 1)
    run_days = result.days_for("running_distance")
    assert len(run_days) == 31

    chicago = {date(2026, 7, d) for d in range(12, 17)}
    for d in run_days:
        if d.plan_on in chicago:
            assert d.kind is PlanDayKind.fixed
            assert d.prescribed_value == pytest.approx(MILE, abs=1e-3)
    assert sum(d.prescribed_value for d in run_days) == pytest.approx(TOTAL, abs=0.5)

    assert len(result.days_for("pushups")) == 10
    assert len(result.days_for("body_weight")) == 10
    assert result.status is FeasibilityStatus.on_track


def test_build_and_store_persists_all_days():
    supa = _FakeSupabase(_july_store())
    user_id = uuid4()
    result = build_and_store_plan(supa, user_id, "2026-07", today=date(2026, 6, 15))

    inserted = supa.captured.get("plan_days", [])
    assert len(inserted) == len(result.days)
    # delete-future ran before reinsert
    assert supa.captured.get("plan_days:deleted")
    # rows carry the user_id and a serializable plan_on
    assert all(r["user_id"] == str(user_id) for r in inserted)
    assert all(isinstance(r["plan_on"], str) for r in inserted)


def test_year_goals_excluded_from_month_plan():
    store = _july_store()
    store["metric_goals"].append(
        {
            "metric_key": "running_distance",
            "kind": "volume",
            "target": 9999,
            "period": "year",
            "qualifier_threshold": None,
            "per_event_min": None,
            "rest_budget": 0,
        }
    )
    supa = _FakeSupabase(store)
    result = build_plan(supa, uuid4(), "2026-07", today=date(2026, 6, 15))
    # The 9999 yearly target would blow the gate if included; plan stays on track.
    assert result.status is FeasibilityStatus.on_track
