"""Tests for run explorer filters (SB-269): weather/temp/pace, on-this-day, sort."""

from __future__ import annotations

from datetime import date
from typing import Any

from src.shared.supabase_ops.runs_repository import RunsRepository


class _CaptureQuery:
    """Records filter calls so we can assert what reached PostgREST."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []

    def _rec(self, op: str, col: str, val: Any) -> _CaptureQuery:
        self.calls.append((op, col, val))
        return self

    def gte(self, col: str, val: Any) -> _CaptureQuery:
        return self._rec("gte", col, val)

    def lte(self, col: str, val: Any) -> _CaptureQuery:
        return self._rec("lte", col, val)

    def eq(self, col: str, val: Any) -> _CaptureQuery:
        return self._rec("eq", col, val)

    def in_(self, col: str, val: Any) -> _CaptureQuery:
        return self._rec("in", col, val)


def _apply(**kwargs: Any) -> _CaptureQuery:
    repo = RunsRepository(supabase=None)  # type: ignore[arg-type]  # query object injected
    q = _CaptureQuery()
    repo._apply_run_filters(q, None, None, None, None, **kwargs)
    return q


def test_weather_temp_pace_filters() -> None:
    q = _apply(weather_type="rainy", temp_min=20, temp_max=30, pace_min=5, pace_max=6)
    assert ("eq", "weather_type", "rainy") in q.calls
    assert ("gte", "temperature_celsius", 20) in q.calls
    assert ("lte", "temperature_celsius", 30) in q.calls
    assert ("gte", "average_pace_min_per_km", 5) in q.calls
    assert ("lte", "average_pace_min_per_km", 6) in q.calls


def test_on_this_day_builds_exact_date_list() -> None:
    q = _apply(on_this_day="07-12")
    op, col, dates = q.calls[0]
    assert (op, col) == ("in", "start_date")
    assert "2014-07-12" in dates
    assert f"{date.today().year}-07-12" in dates
    # Every entry is the same month-day.
    assert all(d.endswith("-07-12") for d in dates)


def test_on_this_day_feb29_skips_non_leap_years() -> None:
    q = _apply(on_this_day="02-29")
    _, _, dates = q.calls[0]
    assert "2024-02-29" in dates  # leap year
    assert not any(d.startswith("2023") for d in dates)  # non-leap skipped


def test_no_extra_filters_no_calls() -> None:
    assert _apply().calls == []
