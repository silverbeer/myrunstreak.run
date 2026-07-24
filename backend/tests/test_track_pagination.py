"""SB-310/311: repo paginates past PostgREST's 1000-row cap.

The bug the backfill verification caught: .limit(10000) is silently capped at
1000 rows per response, so a multi-thousand-run history truncated. These prove
the range-based pagination returns everything.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from src.shared.supabase_ops.runs_repository import RunsRepository

USER = uuid4()
PAGE = 1000


class _RangeCappedTable:
    """Fake PostgREST table that honours .range() and caps a page at 1000 rows,
    exactly like Supabase — so a single query can't see more than 1000."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._lo = 0
        self._hi = PAGE - 1

    def select(self, *_a: Any, **_k: Any) -> _RangeCappedTable:
        return self

    def eq(self, *_a: Any, **_k: Any) -> _RangeCappedTable:
        return self

    @property
    def not_(self) -> _RangeCappedTable:  # for .not_.is_(...)
        return self

    def is_(self, *_a: Any, **_k: Any) -> _RangeCappedTable:
        return self

    def order(self, *_a: Any, **_k: Any) -> _RangeCappedTable:
        return self

    def range(self, lo: int, hi: int) -> _RangeCappedTable:
        self._lo, self._hi = lo, min(hi, lo + PAGE - 1)  # server caps span at 1000
        return self

    def execute(self) -> Any:
        class _R:
            data = self._rows[self._lo : self._hi + 1]

        return _R()


class _Supabase:
    def __init__(self, by_table: dict[str, list[dict[str, Any]]]) -> None:
        self._by_table = by_table

    def table(self, name: str) -> _RangeCappedTable:
        return _RangeCappedTable(self._by_table.get(name, []))


def test_get_all_track_polylines_returns_more_than_one_page() -> None:
    tracks = [{"polyline": f"p{i}", "encoded_precision": 5} for i in range(2500)]
    repo = RunsRepository(_Supabase({"run_tracks": tracks}))  # type: ignore[arg-type]
    out = repo.get_all_track_polylines(USER)
    assert len(out) == 2500  # not truncated to 1000
    assert out[0]["polyline"] == "p0"
    assert out[-1]["polyline"] == "p2499"


def test_missing_tracks_count_spans_full_history() -> None:
    gps = [
        {"id": f"r{i}", "source_activity_id": f"a{i}", "start_date": "2020-01-01"}
        for i in range(4203)
    ]
    stored = [{"run_id": f"r{i}"} for i in range(100)]  # only 100 backfilled so far
    repo = RunsRepository(_Supabase({"runs": gps, "run_tracks": stored}))  # type: ignore[arg-type]
    # The real remaining is 4103, not the capped 900 the bug reported.
    assert repo.count_runs_missing_tracks(USER) == 4103
    # A bounded batch still returns just `limit` runs, oldest first.
    batch = repo.get_runs_missing_tracks(USER, limit=100)
    assert len(batch) == 100
    assert batch[0]["id"] == "r100"  # first un-stored run
