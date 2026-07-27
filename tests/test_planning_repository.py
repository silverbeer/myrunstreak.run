"""Tests for the planning repositories (SB-164) against a fake Supabase client.

Same shape as the ``_FakeSupabase``/``_FakeQuery`` pattern in
``test_planning_service.py``, but the query stub *records* every chained call so
the tests can assert the table, the eq/gte/lte filters, the ordering, and the
insert/upsert/delete payload — no live DB, no RLS.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from src.shared.supabase_ops import (
    PlanConstraintsRepository,
    PlanDaysRepository,
    ReadinessRepository,
)


# --------------------------------------------------------------------------- #
# Recording fake Supabase
# --------------------------------------------------------------------------- #
class _FakeQuery:
    """Chainable query stub that records its calls and returns canned rows.

    ``store[table]`` supplies select rows; ``store[f"{table}:deleted"]`` supplies
    what a delete reports back (PostgREST returns the deleted rows).
    """

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

    def insert(self, payload: Any) -> _FakeQuery:
        self.mode, self.payload = "insert", payload
        return self._rec("insert", payload)

    def upsert(self, payload: Any, **k: Any) -> _FakeQuery:
        self.mode, self.payload = "upsert", payload
        return self._rec("upsert", payload, **k)

    def delete(self) -> _FakeQuery:
        self.mode = "delete"
        return self._rec("delete")

    def execute(self) -> SimpleNamespace:
        if self.mode in ("insert", "upsert"):
            rows = self.payload if isinstance(self.payload, list) else [self.payload]
            return SimpleNamespace(data=rows)
        if self.mode == "delete":
            return SimpleNamespace(data=list(self.store.get(f"{self.table}:deleted", [])))
        return SimpleNamespace(data=list(self.store.get(self.table, [])))

    # -- assertion helpers --------------------------------------------------
    def args_of(self, name: str) -> list[tuple[Any, ...]]:
        """Positional args of every recorded call to ``name``, in order."""
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
        """The single query this client issued (fails loudly if there wasn't one)."""
        assert len(self.queries) == 1, f"expected 1 query, got {len(self.queries)}"
        return self.queries[0]


USER_ID = uuid4()


# --------------------------------------------------------------------------- #
# PlanConstraintsRepository
# --------------------------------------------------------------------------- #
def test_constraints_create_stamps_user_id_and_returns_row() -> None:
    supabase = _FakeSupabase()
    repo = PlanConstraintsRepository(supabase)  # type: ignore[arg-type]

    row = repo.create(
        USER_ID,
        {"metric_key": "running_distance", "start_on": "2026-07-01", "end_on": "2026-07-05"},
    )

    q = supabase.only()
    assert q.table == "plan_constraints"
    assert q.mode == "insert"
    assert q.payload == {
        "metric_key": "running_distance",
        "start_on": "2026-07-01",
        "end_on": "2026-07-05",
        "user_id": str(USER_ID),
    }
    assert row["user_id"] == str(USER_ID)


def test_constraints_list_scopes_by_user_and_orders() -> None:
    stored = [{"id": str(uuid4()), "metric_key": "running_distance"}]
    supabase = _FakeSupabase({"plan_constraints": stored})
    repo = PlanConstraintsRepository(supabase)  # type: ignore[arg-type]

    rows = repo.list(USER_ID)

    q = supabase.only()
    assert q.table == "plan_constraints"
    assert q.args_of("eq") == [("user_id", str(USER_ID))]
    assert q.args_of("gte") == [] and q.args_of("lte") == []
    assert q.args_of("order") == [("start_on",)]
    assert rows == stored


def test_constraints_list_window_filters_are_overlap_not_containment() -> None:
    supabase = _FakeSupabase({"plan_constraints": []})
    repo = PlanConstraintsRepository(supabase)  # type: ignore[arg-type]

    repo.list(USER_ID, date_from=date(2026, 7, 1), date_to=date(2026, 7, 31))

    q = supabase.only()
    # starts on/before the window end, ends on/after the window start
    assert q.args_of("lte") == [("start_on", "2026-07-31")]
    assert q.args_of("gte") == [("end_on", "2026-07-01")]


@pytest.mark.parametrize(
    ("deleted_rows", "expected"),
    [([{"id": "x"}], True), ([], False)],
)
def test_constraints_delete_reports_whether_a_row_went(
    deleted_rows: list[dict[str, Any]], expected: bool
) -> None:
    constraint_id = uuid4()
    supabase = _FakeSupabase({"plan_constraints:deleted": deleted_rows})
    repo = PlanConstraintsRepository(supabase)  # type: ignore[arg-type]

    assert repo.delete(USER_ID, constraint_id) is expected

    q = supabase.only()
    assert q.mode == "delete"
    # Scoped by both id and user_id — a user can't delete someone else's row.
    assert q.args_of("eq") == [("id", str(constraint_id)), ("user_id", str(USER_ID))]


# --------------------------------------------------------------------------- #
# ReadinessRepository
# --------------------------------------------------------------------------- #
def test_readiness_upsert_targets_the_one_row_per_day_constraint() -> None:
    supabase = _FakeSupabase()
    repo = ReadinessRepository(supabase)  # type: ignore[arg-type]

    row = repo.upsert(USER_ID, {"log_on": "2026-07-14", "status": "tired"})

    q = supabase.only()
    assert q.table == "readiness_log"
    assert q.payload == {"log_on": "2026-07-14", "status": "tired", "user_id": str(USER_ID)}
    assert q.kwargs_of("upsert") == [{"on_conflict": "user_id,log_on"}]
    assert row["status"] == "tired"


def test_readiness_list_filters_by_log_on_window() -> None:
    stored = [{"log_on": "2026-07-14", "status": "good"}]
    supabase = _FakeSupabase({"readiness_log": stored})
    repo = ReadinessRepository(supabase)  # type: ignore[arg-type]

    rows = repo.list(USER_ID, date_from=date(2026, 7, 1), date_to=date(2026, 7, 31))

    q = supabase.only()
    assert q.args_of("eq") == [("user_id", str(USER_ID))]
    assert q.args_of("gte") == [("log_on", "2026-07-01")]
    assert q.args_of("lte") == [("log_on", "2026-07-31")]
    assert q.args_of("order") == [("log_on",)]
    assert rows == stored


def test_readiness_list_without_bounds_applies_no_range_filters() -> None:
    supabase = _FakeSupabase({"readiness_log": []})
    repo = ReadinessRepository(supabase)  # type: ignore[arg-type]

    assert repo.list(USER_ID) == []

    q = supabase.only()
    assert q.args_of("gte") == [] and q.args_of("lte") == []


# --------------------------------------------------------------------------- #
# PlanDaysRepository
# --------------------------------------------------------------------------- #
def test_plan_days_replace_from_deletes_the_future_then_inserts() -> None:
    supabase = _FakeSupabase()
    repo = PlanDaysRepository(supabase)  # type: ignore[arg-type]

    rows = [
        {"metric_key": "running_distance", "plan_on": "2026-07-14", "prescribed_value": 8.0},
        {"metric_key": "running_distance", "plan_on": "2026-07-15", "prescribed_value": 5.0},
    ]
    written = repo.replace_from(USER_ID, date(2026, 7, 14), rows)

    delete_q, insert_q = supabase.queries
    assert delete_q.table == "plan_days" and delete_q.mode == "delete"
    assert delete_q.args_of("eq") == [("user_id", str(USER_ID))]
    # Only on/after from_date — past prescriptions stay as the record of what was asked.
    assert delete_q.args_of("gte") == [("plan_on", "2026-07-14")]

    assert insert_q.mode == "insert"
    assert [r["plan_on"] for r in insert_q.payload] == ["2026-07-14", "2026-07-15"]
    assert {r["user_id"] for r in insert_q.payload} == {str(USER_ID)}
    assert len(written) == 2


def test_plan_days_replace_from_with_no_rows_still_clears_and_skips_insert() -> None:
    supabase = _FakeSupabase()
    repo = PlanDaysRepository(supabase)  # type: ignore[arg-type]

    assert repo.replace_from(USER_ID, date(2026, 7, 14), []) == []

    q = supabase.only()  # the delete only — no empty insert
    assert q.mode == "delete"


def test_plan_days_replace_from_does_not_mutate_caller_rows() -> None:
    supabase = _FakeSupabase()
    repo = PlanDaysRepository(supabase)  # type: ignore[arg-type]

    rows = [{"metric_key": "running_distance", "plan_on": "2026-07-14"}]
    repo.replace_from(USER_ID, date(2026, 7, 14), rows)

    assert "user_id" not in rows[0]


def test_plan_days_list_filters_by_plan_on_window() -> None:
    stored = [{"plan_on": "2026-07-14", "prescribed_value": 8.0}]
    supabase = _FakeSupabase({"plan_days": stored})
    repo = PlanDaysRepository(supabase)  # type: ignore[arg-type]

    rows = repo.list(USER_ID, date_from=date(2026, 7, 1), date_to=date(2026, 7, 31))

    q = supabase.only()
    assert q.table == "plan_days"
    assert q.args_of("eq") == [("user_id", str(USER_ID))]
    assert q.args_of("gte") == [("plan_on", "2026-07-01")]
    assert q.args_of("lte") == [("plan_on", "2026-07-31")]
    assert q.args_of("order") == [("plan_on",)]
    assert rows == stored


def test_plan_days_list_without_bounds_returns_everything_for_the_user() -> None:
    stored = [{"plan_on": "2026-07-14"}, {"plan_on": "2026-07-15"}]
    supabase = _FakeSupabase({"plan_days": stored})
    repo = PlanDaysRepository(supabase)  # type: ignore[arg-type]

    assert repo.list(USER_ID) == stored

    q = supabase.only()
    assert q.args_of("gte") == [] and q.args_of("lte") == []
