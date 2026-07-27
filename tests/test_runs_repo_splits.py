"""Tests for the splits-related RunsRepository methods against a fake client.

Covers ``set_has_splits``, ``get_runs_missing_splits``, ``get_runs_with_splits``
and ``get_splits_for_run`` — the surface the splits backfill and /stats/splits
depend on. Same ``_FakeSupabase``/``_FakeQuery`` idea as
``test_planning_service.py``, but the query stub records every chained call so
the table, filters, ordering and limit can be asserted. No live DB.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from src.shared.supabase_ops import RunsRepository


# --------------------------------------------------------------------------- #
# Recording fake Supabase
# --------------------------------------------------------------------------- #
class _FakeQuery:
    """Chainable query stub: records its calls, serves ``store[table]`` rows."""

    def __init__(self, table: str, store: dict[str, Any], log: list[_FakeQuery]):
        self.table = table
        self.store = store
        self.ops: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.mode = "select"
        self.payload: Any = None
        log.append(self)

    def _rec(self, name: str, *a: Any, **k: Any) -> _FakeQuery:
        self.ops.append((name, a, k))
        return self

    def select(self, *a: Any, **k: Any) -> _FakeQuery:
        return self._rec("select", *a, **k)

    def eq(self, *a: Any, **k: Any) -> _FakeQuery:
        return self._rec("eq", *a, **k)

    def gte(self, *a: Any, **k: Any) -> _FakeQuery:
        return self._rec("gte", *a, **k)

    def lte(self, *a: Any, **k: Any) -> _FakeQuery:
        return self._rec("lte", *a, **k)

    def order(self, *a: Any, **k: Any) -> _FakeQuery:
        return self._rec("order", *a, **k)

    def limit(self, *a: Any, **k: Any) -> _FakeQuery:
        return self._rec("limit", *a, **k)

    def update(self, payload: Any) -> _FakeQuery:
        self.mode, self.payload = "update", payload
        return self._rec("update", payload)

    def execute(self) -> SimpleNamespace:
        if self.mode == "update":
            return SimpleNamespace(data=[self.payload])
        return SimpleNamespace(data=list(self.store.get(self.table, [])))

    # -- assertion helpers --------------------------------------------------
    def args_of(self, name: str) -> list[tuple[Any, ...]]:
        return [a for n, a, _ in self.ops if n == name]

    def kwargs_of(self, name: str) -> list[dict[str, Any]]:
        return [k for n, _, k in self.ops if n == name]


class _FakeSupabase:
    def __init__(self, store: dict[str, Any] | None = None):
        self.store = store or {}
        self.queries: list[_FakeQuery] = []

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(name, self.store, self.queries)

    def only(self) -> _FakeQuery:
        assert len(self.queries) == 1, f"expected 1 query, got {len(self.queries)}"
        return self.queries[0]


USER_ID = uuid4()


def _repo(store: dict[str, Any] | None = None) -> tuple[RunsRepository, _FakeSupabase]:
    supabase = _FakeSupabase(store)
    return RunsRepository(supabase), supabase  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# set_has_splits
# --------------------------------------------------------------------------- #
def test_set_has_splits_defaults_to_true() -> None:
    run_id = uuid4()
    repo, supabase = _repo()

    repo.set_has_splits(run_id)

    q = supabase.only()
    assert q.table == "runs"
    assert q.mode == "update"
    assert q.payload == {"has_splits": True}
    assert q.args_of("eq") == [("id", str(run_id))]


def test_set_has_splits_can_clear_the_flag() -> None:
    run_id = uuid4()
    repo, supabase = _repo()

    repo.set_has_splits(run_id, False)

    q = supabase.only()
    assert q.payload == {"has_splits": False}


# --------------------------------------------------------------------------- #
# get_splits_for_run
# --------------------------------------------------------------------------- #
def test_get_splits_for_run_orders_by_split_number() -> None:
    run_id = uuid4()
    stored = [
        {"split_number": 1, "cumulative_distance_km": 1.6, "cumulative_seconds": 600},
        {"split_number": 2, "cumulative_distance_km": 3.2, "cumulative_seconds": 1140},
    ]
    repo, supabase = _repo({"splits": stored})

    assert repo.get_splits_for_run(run_id) == stored

    q = supabase.only()
    assert q.table == "splits"
    assert q.args_of("eq") == [("run_id", str(run_id))]
    assert q.args_of("order") == [("split_number",)]


# --------------------------------------------------------------------------- #
# get_runs_with_splits
# --------------------------------------------------------------------------- #
def test_get_runs_with_splits_selects_flagged_runs_newest_first() -> None:
    stored = [{"id": str(uuid4()), "start_date": "2026-07-14", "distance_km": 8.0}]
    repo, supabase = _repo({"runs": stored})

    assert repo.get_runs_with_splits(USER_ID) == stored

    q = supabase.only()
    assert q.table == "runs"
    assert q.args_of("select") == [("id, start_date, distance_km",)]
    assert q.args_of("eq") == [("user_id", str(USER_ID)), ("has_splits", True)]
    assert q.args_of("gte") == [] and q.args_of("lte") == []
    assert q.args_of("order") == [("start_date",)]
    assert q.kwargs_of("order") == [{"desc": True}]
    assert q.args_of("limit") == [(30,)]


def test_get_runs_with_splits_applies_date_window_and_limit() -> None:
    repo, supabase = _repo({"runs": []})

    repo.get_runs_with_splits(USER_ID, since=date(2026, 6, 1), until=date(2026, 6, 30), limit=5)

    q = supabase.only()
    assert q.args_of("gte") == [("start_date", "2026-06-01")]
    assert q.args_of("lte") == [("start_date", "2026-06-30")]
    assert q.args_of("limit") == [(5,)]


# --------------------------------------------------------------------------- #
# get_runs_missing_splits
# --------------------------------------------------------------------------- #
def test_get_runs_missing_splits_is_the_has_splits_false_complement() -> None:
    stored = [{"id": str(uuid4()), "source_activity_id": "abc", "start_date": "2026-07-14"}]
    repo, supabase = _repo({"runs": stored})

    assert repo.get_runs_missing_splits(USER_ID) == stored

    q = supabase.only()
    assert q.table == "runs"
    # Backfill only needs enough to fetch the splits from the source.
    assert q.args_of("select") == [("id, source_activity_id, start_date",)]
    assert q.args_of("eq") == [("user_id", str(USER_ID)), ("has_splits", False)]
    assert q.args_of("order") == [("start_date",)]
    assert q.kwargs_of("order") == [{"desc": True}]
    assert q.args_of("limit") == [(100,)]


def test_get_runs_missing_splits_applies_date_window_and_limit() -> None:
    repo, supabase = _repo({"runs": []})

    repo.get_runs_missing_splits(USER_ID, since=date(2026, 1, 1), until=date(2026, 3, 31), limit=10)

    q = supabase.only()
    assert q.args_of("gte") == [("start_date", "2026-01-01")]
    assert q.args_of("lte") == [("start_date", "2026-03-31")]
    assert q.args_of("limit") == [(10,)]


def test_get_runs_missing_splits_since_only_leaves_upper_bound_open() -> None:
    repo, supabase = _repo({"runs": []})

    repo.get_runs_missing_splits(USER_ID, since=date(2026, 1, 1))

    q = supabase.only()
    assert q.args_of("gte") == [("start_date", "2026-01-01")]
    assert q.args_of("lte") == []
