"""Round-trip tests for the workout repositories (SB-191), via a fake client."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from src.shared.supabase_ops.workout_repository import (
    WorkoutSessionsRepository,
    WorkoutTemplatesRepository,
)


class _FakeQuery:
    def __init__(self, table: str, store: dict):
        self.table = table
        self.store = store
        self._mode = "select"
        self._payload: Any = None

    def select(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def eq(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def is_(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def gte(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def lte(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def order(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def limit(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def insert(self, payload: Any) -> _FakeQuery:
        self._mode, self._payload = "insert", payload
        return self

    def update(self, payload: Any) -> _FakeQuery:
        self._mode, self._payload = "update", payload
        return self

    def in_(self, *a: Any, **k: Any) -> _FakeQuery:
        return self

    def delete(self) -> _FakeQuery:
        self._mode = "delete"
        return self

    def execute(self) -> SimpleNamespace:
        if self._mode == "insert":
            rows = self._payload if isinstance(self._payload, list) else [self._payload]
            out = []
            for r in rows:
                row = {"id": str(uuid4()), **r} if "id" not in r else dict(r)
                self.store.setdefault(self.table, []).append(row)
                out.append(row)
            return SimpleNamespace(data=out)
        if self._mode == "update":
            rows = self.store.get(self.table, [])
            for r in rows:
                r.update(self._payload)
            return SimpleNamespace(data=rows)
        if self._mode == "delete":
            data = self.store.get(self.table, [])
            self.store[self.table] = []
            return SimpleNamespace(data=data)
        return SimpleNamespace(data=list(self.store.get(self.table, [])))


class _FakeSupabase:
    def __init__(self) -> None:
        self.store: dict[str, list[dict[str, Any]]] = {}

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(name, self.store)


def test_template_create_round_trips_with_items():
    supa = _FakeSupabase()
    repo = WorkoutTemplatesRepository(supa)
    user = uuid4()
    out = repo.create(
        user,
        {
            "name": "Saturday Circuit",
            "type": "circuit",
            "rounds": 3,
            "items": [
                {"exercise_key": "jump_rope", "position": 0, "target_duration_seconds": 180},
                {"exercise_key": "pushups", "position": 1, "target_duration_seconds": 30},
            ],
        },
    )
    assert out["name"] == "Saturday Circuit"
    assert out["rounds"] == 3
    assert len(out["items"]) == 2
    assert all(i["user_id"] == str(user) for i in out["items"])
    assert all(i["template_id"] == out["id"] for i in out["items"])


def test_template_item_broken_rep_round_trips():
    """Segment goals + a pace range survive create -> read (SB-264)."""
    supa = _FakeSupabase()
    repo = WorkoutTemplatesRepository(supa)
    out = repo.create(
        uuid4(),
        {
            "name": "Track Thursday",
            "type": "intervals",
            "items": [
                {
                    "exercise_key": "interval_run",
                    "position": 0,
                    "target_distance_m": 400,
                    "target_duration_seconds": 20,
                    "target_duration_max_seconds": 22,
                    "segments": [
                        {
                            "distance_m": 100,
                            "target_s_min": 20,
                            "target_s_max": 22,
                            "label": "0-100",
                        },
                        {"distance_m": 100, "target_s_min": 15, "label": "100-200"},
                    ],
                }
            ],
        },
    )
    item = out["items"][0]
    assert item["target_duration_max_seconds"] == 22
    assert len(item["segments"]) == 2
    assert item["segments"][0] == {
        "distance_m": 100,
        "target_s_min": 20,
        "target_s_max": 22,
        "label": "0-100",
    }
    assert item["segments"][1]["target_s_min"] == 15


def test_template_update_replaces_items_and_fields():
    supa = _FakeSupabase()
    repo = WorkoutTemplatesRepository(supa)
    user = uuid4()
    out = repo.create(
        user,
        {
            "name": "A",
            "type": "circuit",
            "rounds": 2,
            "items": [{"exercise_key": "pushups", "position": 0, "target_reps": 10}],
        },
    )
    upd = repo.update(
        user,
        UUID(out["id"]),
        {
            "name": "B",
            "rounds": 3,
            "items": [{"exercise_key": "plank", "position": 0, "target_duration_seconds": 60}],
        },
    )
    assert upd is not None
    assert upd["name"] == "B"
    assert upd["rounds"] == 3
    assert len(upd["items"]) == 1
    assert upd["items"][0]["exercise_key"] == "plank"


def test_template_create_round_trips_scheduled_for():
    """An optional scheduled_for date survives create -> read (SB-335)."""
    supa = _FakeSupabase()
    repo = WorkoutTemplatesRepository(supa)
    out = repo.create(
        uuid4(),
        {"name": "Monday", "type": "circuit", "rounds": 1, "scheduled_for": "2026-07-28"},
    )
    assert out["scheduled_for"] == "2026-07-28"


def test_list_attaches_completion_state():
    """list() marks a template done when a session references it, keeping the
    latest session_date; untouched templates report has_session False (SB-334)."""
    supa = _FakeSupabase()
    user = uuid4()
    t1, t2 = str(uuid4()), str(uuid4())
    supa.store["workout_templates"] = [
        {"id": t1, "user_id": str(user), "name": "A", "type": "circuit", "rounds": 1},
        {"id": t2, "user_id": str(user), "name": "B", "type": "circuit", "rounds": 1},
    ]
    supa.store["workout_sessions"] = [
        {"template_id": t1, "session_date": "2026-07-21"},
        {"template_id": t1, "session_date": "2026-07-23"},  # latest wins
    ]
    repo = WorkoutTemplatesRepository(supa)
    by_id = {r["id"]: r for r in repo.list(user)}

    assert by_id[t1]["has_session"] is True
    assert by_id[t1]["last_session_date"] == "2026-07-23"
    assert by_id[t2]["has_session"] is False
    assert by_id[t2]["last_session_date"] is None


def test_session_create_round_trips_with_sets():
    supa = _FakeSupabase()
    repo = WorkoutSessionsRepository(supa)
    user = uuid4()
    out = repo.create(
        user,
        {
            "session_date": "2026-06-20",
            "type": "test",
            "sets": [
                {"exercise_key": "40yd_dash", "distance_m": 36.58, "time_seconds": 5.42},
                {"exercise_key": "pushups", "round_number": 1, "reps": 22},
            ],
        },
    )
    assert out["session_date"] == "2026-06-20"
    assert len(out["sets"]) == 2
    dash = next(s for s in out["sets"] if s["exercise_key"] == "40yd_dash")
    assert dash["time_seconds"] == 5.42
    assert all(s["session_id"] == out["id"] for s in out["sets"])


def test_template_item_option_group_round_trips():
    """Alternatives survive create -> read (SB-448).

    Matthew's in-season aerobic day is run OR bike OR jump rope; without the
    group the card prescribes all three.
    """
    supa = _FakeSupabase()
    repo = WorkoutTemplatesRepository(supa)
    out = repo.create(
        uuid4(),
        {
            "name": "In-season aerobic day",
            "type": "session",
            "items": [
                {
                    "exercise_key": "easy_jog",
                    "position": 0,
                    "target_duration_seconds": 1200,
                    "option_group": "aerobic",
                    "option_group_label": "Aerobic engine",
                },
                {
                    "exercise_key": "bike",
                    "position": 1,
                    "target_duration_seconds": 2400,
                    "option_group": "aerobic",
                },
                {"exercise_key": "plank", "position": 2, "target_duration_seconds": 60},
            ],
        },
    )

    by_key = {i["exercise_key"]: i for i in out["items"]}
    assert by_key["easy_jog"]["option_group"] == "aerobic"
    assert by_key["easy_jog"]["option_group_label"] == "Aerobic engine"
    assert by_key["bike"]["option_group"] == "aerobic"
    # The label lives on one member; the renderers read it from whichever has it.
    assert by_key["bike"].get("option_group_label") is None
    # A mandatory item stays mandatory.
    assert by_key["plank"].get("option_group") is None


def test_template_items_without_option_group_are_unchanged():
    """Every existing template has NULL groups and must behave exactly as before."""
    supa = _FakeSupabase()
    repo = WorkoutTemplatesRepository(supa)
    out = repo.create(
        uuid4(),
        {
            "name": "Monday Circuit",
            "type": "circuit",
            "items": [{"exercise_key": "pushups", "position": 0, "target_reps": 15}],
        },
    )
    assert out["items"][0].get("option_group") is None


def test_template_item_range_targets_round_trip():
    """Ranged reps/load/rest survive create -> read (SB-446).

    The 2026-07-30 speed-endurance block: "8-12x200 at 40-42 seconds,
    60-90 second rest (go off how you feel)".
    """
    supa = _FakeSupabase()
    repo = WorkoutTemplatesRepository(supa)
    out = repo.create(
        uuid4(),
        {
            "name": "Speed endurance",
            "type": "intervals",
            "items": [
                {
                    "exercise_key": "interval_run",
                    "position": 0,
                    "target_reps": 8,
                    "target_reps_max": 12,
                    "target_distance_m": 200,
                    "target_duration_seconds": 40,
                    "target_duration_max_seconds": 42,
                    "rest_seconds": 60,
                    "rest_seconds_max": 90,
                    "rest_mode": "autoregulated",
                },
                {
                    "exercise_key": "ground_start_accel",
                    "position": 1,
                    "target_reps": 4,
                    "rest_mode": "full",
                },
            ],
        },
    )

    intervals, accels = out["items"][0], out["items"][1]
    assert (intervals["target_reps"], intervals["target_reps_max"]) == (8, 12)
    assert (intervals["rest_seconds"], intervals["rest_seconds_max"]) == (60, 90)
    assert intervals["rest_mode"] == "autoregulated"
    # "Full recovery" carries no number — that is the point of the mode.
    assert accels["rest_mode"] == "full"
    assert accels.get("rest_seconds") is None


def test_template_item_without_ranges_is_unchanged():
    """Every existing item has NULL maxima and must behave exactly as before."""
    supa = _FakeSupabase()
    repo = WorkoutTemplatesRepository(supa)
    out = repo.create(
        uuid4(),
        {
            "name": "Monday Circuit",
            "type": "circuit",
            "items": [{"exercise_key": "pushups", "position": 0, "target_reps": 15}],
        },
    )
    item = out["items"][0]
    assert item["target_reps"] == 15
    assert item.get("target_reps_max") is None
    assert item.get("rest_mode") is None
