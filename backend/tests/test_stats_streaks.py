"""Regression tests for the /stats/streaks endpoint fetch (SB-209, SB-210).

SB-209: `_streaks` used a single `.limit(10000)` query, but PostgREST caps a
response at ~1000 rows server-side, silently truncating to the oldest ~1000
runs. For a user with >1000 runs that dropped every recent run and made the
current streak read as 0. The fix pages with `.range()` until exhausted.

SB-210: `_streaks` also returns `current_streak_km` / `longest_streak_km`,
the summed distance over each streak's date window.

The fake client below is paging-aware: `.range(offset, end)` narrows what the
next `.execute()` returns, so a query that fails to paginate would see only the
first 1000-row window — exactly the truncation this guards against.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch
from uuid import uuid4

from backend.routes import stats

PAGE = 1000


class _PagingQuery:
    """Records the active range() window and slices rows on execute()."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._range: tuple[int, int] | None = None
        self.range_calls: list[tuple[int, int]] = []

    def select(self, *a: Any, **k: Any) -> _PagingQuery:
        return self

    def eq(self, *a: Any, **k: Any) -> _PagingQuery:
        return self

    def order(self, *a: Any, **k: Any) -> _PagingQuery:
        return self

    def range(self, start: int, end: int) -> _PagingQuery:
        self._range = (start, end)
        self.range_calls.append((start, end))
        return self

    def execute(self) -> SimpleNamespace:
        if self._range is None:
            return SimpleNamespace(data=list(self._rows))
        start, end = self._range
        # PostgREST range is inclusive; also cap the window at PAGE rows to
        # mimic the server-side db-max-rows ceiling that caused SB-209.
        window = self._rows[start : min(end + 1, start + PAGE)]
        return SimpleNamespace(data=window)


class _PagingClient:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.query = _PagingQuery(rows)

    def table(self, _name: str) -> _PagingQuery:
        return self.query


def _daily_rows(n: int, end: date, km: float) -> list[dict[str, Any]]:
    """n consecutive daily runs ending on `end`, oldest first."""
    start = end - timedelta(days=n - 1)
    return [
        {"start_date": (start + timedelta(days=i)).isoformat(), "distance_km": km} for i in range(n)
    ]


async def test_streaks_pages_past_1000_rows_and_reports_full_streak() -> None:
    """SB-209: >1000 consecutive runs must not truncate to a 0 current streak."""
    end = date(2026, 7, 1)
    rows = _daily_rows(1500, end, km=5.0)
    client = _PagingClient(rows)

    with (
        patch.object(stats, "get_supabase_client", return_value=client),
        patch.object(stats, "_today_local", return_value=end),
    ):
        result = await stats._streaks(uuid4())

    # Would be 0 (or 1000) under the truncating single-query bug.
    assert result["current_streak"] == 1500
    assert result["longest_streak"] == 1500
    # Paged, didn't stop at the first window.
    assert client.query.range_calls[0] == (0, PAGE - 1)
    assert len(client.query.range_calls) >= 2


async def test_streaks_reports_streak_mileage() -> None:
    """SB-210: current/longest streak km == summed distance over the window."""
    end = date(2026, 7, 1)
    rows = _daily_rows(1500, end, km=5.0)
    client = _PagingClient(rows)

    with (
        patch.object(stats, "get_supabase_client", return_value=client),
        patch.object(stats, "_today_local", return_value=end),
    ):
        result = await stats._streaks(uuid4())

    assert result["current_streak_km"] == 1500 * 5.0
    assert result["longest_streak_km"] == 1500 * 5.0


async def test_streaks_empty_history_is_zeroed() -> None:
    client = _PagingClient([])

    with (
        patch.object(stats, "get_supabase_client", return_value=client),
        patch.object(stats, "_today_local", return_value=date(2026, 7, 1)),
    ):
        result = await stats._streaks(uuid4())

    assert result["current_streak"] == 0
    assert result["current_streak_km"] == 0.0
    assert result["longest_streak"] == 0
    assert result["longest_streak_km"] == 0.0
