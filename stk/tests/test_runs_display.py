"""SB-306: the runs table surfaces the activity id (for stk route show / audio)."""

from __future__ import annotations

from typing import Any

from cli import display
from rich.console import Console


def _render(data: dict[str, Any]) -> str:
    # Render to a string buffer so we can assert on the visible table text.
    console = Console(record=True, width=120)
    original = display.console
    display.console = console
    try:
        display.display_recent_runs(data)
    finally:
        display.console = original
    return console.export_text()


def _run(**over: Any) -> dict[str, Any]:
    base = {
        "date": "2026-07-22T09:16:00",
        "distance_km": 6.88,
        "duration_minutes": 34.5,
        "avg_pace_min_per_km": 6.05,
        "heart_rate_avg": 140,
        "temperature_celsius": 24,
        "weather": "cloudy",
        "activity_id": "46444589",
    }
    base.update(over)
    return base


def test_runs_table_shows_activity_id() -> None:
    out = _render({"count": 1, "runs": [_run()]})
    assert "ID" in out  # column header
    assert "46444589" in out  # the id you pass to `stk route show`


def test_totals_row_column_count_matches() -> None:
    # A totals row with the wrong cell count raises; rendering two runs exercises it.
    out = _render({"count": 2, "runs": [_run(), _run(activity_id="46431098")]})
    assert "46431098" in out
    assert "2 runs" in out
