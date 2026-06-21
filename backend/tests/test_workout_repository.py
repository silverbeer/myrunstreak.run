"""Round-trip tests for the workout repositories (SB-191), via a fake client."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

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
