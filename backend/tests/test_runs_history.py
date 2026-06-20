"""SB-184: full-history access — runs filters/count + metrics paging.

Uses a recording fake supabase client so we can assert the exact query chain
(gte/lte/range/count) the repos build, without a live database.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from src.shared.supabase_ops.metrics_repository import MetricEntriesRepository
from src.shared.supabase_ops.runs_repository import RunsRepository


class _RecQuery:
    """Records every chained call; returns canned data + count on execute()."""

    def __init__(self, rows: list[dict[str, Any]], count: int | None) -> None:
        self.rows = rows
        self.count = count
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def _rec(self, name: str, *a: Any, **k: Any) -> _RecQuery:
        self.calls.append((name, a, k))
        return self

    def select(self, *a: Any, **k: Any) -> _RecQuery:
        return self._rec("select", *a, **k)

    def eq(self, *a: Any, **k: Any) -> _RecQuery:
        return self._rec("eq", *a, **k)

    def gte(self, *a: Any, **k: Any) -> _RecQuery:
        return self._rec("gte", *a, **k)

    def lte(self, *a: Any, **k: Any) -> _RecQuery:
        return self._rec("lte", *a, **k)

    def order(self, *a: Any, **k: Any) -> _RecQuery:
        return self._rec("order", *a, **k)

    def range(self, *a: Any, **k: Any) -> _RecQuery:
        return self._rec("range", *a, **k)

    def limit(self, *a: Any, **k: Any) -> _RecQuery:
        return self._rec("limit", *a, **k)

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.rows, count=self.count)

    def filter_calls(self, name: str) -> list[tuple[Any, ...]]:
        return [a for n, a, _ in self.calls if n == name]


class _FakeClient:
    def __init__(self, rows: list[dict[str, Any]] | None = None, count: int | None = None) -> None:
        self.query = _RecQuery(rows or [], count)

    def table(self, _name: str) -> _RecQuery:
        return self.query


def test_get_runs_by_user_applies_date_and_distance_filters() -> None:
    client = _FakeClient(rows=[{"id": "1"}])
    repo = RunsRepository(client)  # type: ignore[arg-type]
    uid = uuid4()

    out = repo.get_runs_by_user(
        uid,
        limit=366,
        offset=0,
        date_from=date(2016, 1, 1),
        date_to=date(2016, 12, 31),
        distance_min=42.0,
        distance_max=50.0,
    )

    assert out == [{"id": "1"}]
    gte = client.query.filter_calls("gte")
    lte = client.query.filter_calls("lte")
    assert ("start_date", "2016-01-01") in gte
    assert ("distance_km", 42.0) in gte
    assert ("start_date", "2016-12-31") in lte
    assert ("distance_km", 50.0) in lte
    # paging window: range(offset, offset + limit - 1)
    assert client.query.filter_calls("range") == [(0, 365)]


def test_get_runs_by_user_no_filters_skips_clauses() -> None:
    client = _FakeClient(rows=[])
    RunsRepository(client).get_runs_by_user(uuid4(), limit=50)  # type: ignore[arg-type]
    assert client.query.filter_calls("gte") == []
    assert client.query.filter_calls("lte") == []


def test_count_runs_by_user_returns_count_with_filters() -> None:
    client = _FakeClient(count=4740)
    repo = RunsRepository(client)  # type: ignore[arg-type]

    n = repo.count_runs_by_user(uuid4(), distance_min=42.0)

    assert n == 4740
    assert ("distance_km", 42.0) in client.query.filter_calls("gte")


def test_count_runs_by_user_none_count_is_zero() -> None:
    client = _FakeClient(count=None)
    assert RunsRepository(client).count_runs_by_user(uuid4()) == 0  # type: ignore[arg-type]


async def test_runs_route_passes_filters_to_repo() -> None:
    from unittest.mock import MagicMock, patch

    import pytest

    pytest.importorskip("fastapi")
    from backend.routes.runs import list_runs

    repo = MagicMock()
    repo.get_runs_by_user.return_value = []
    repo.count_runs_by_user.return_value = 0
    uid = uuid4()

    with (
        patch("backend.routes.runs.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.runs.RunsRepository", return_value=repo),
    ):
        result = await list_runs(
            user_id=uid,
            offset=0,
            limit=366,
            date_from=date(2016, 1, 1),
            date_to=date(2016, 12, 31),
            distance_min=42.0,
            distance_max=None,
        )

    assert result["total"] == 0
    _, kwargs = repo.get_runs_by_user.call_args
    assert kwargs["date_from"] == date(2016, 1, 1)
    assert kwargs["distance_min"] == 42.0
    assert kwargs["limit"] == 366
    # count uses the same filters so pagination totals match the filtered set
    _, ckwargs = repo.count_runs_by_user.call_args
    assert ckwargs["date_to"] == date(2016, 12, 31)


def test_metric_entries_list_pages_with_offset() -> None:
    client = _FakeClient(rows=[{"id": "e"}])
    repo = MetricEntriesRepository(client)  # type: ignore[arg-type]

    repo.list(uuid4(), limit=2000, offset=2000)

    # offset paging via range(offset, offset + limit - 1) — reaches old data
    assert client.query.filter_calls("range") == [(2000, 3999)]
    assert client.query.filter_calls("limit") == []  # no longer a bare .limit()
