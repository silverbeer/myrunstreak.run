"""SB-477: the verify report renders its findings, and says so when there are none."""

from __future__ import annotations

from typing import Any

from cli import display
from rich.console import Console


def _render(data: dict[str, Any]) -> str:
    console = Console(record=True, width=120)
    original = display.console
    display.console = console
    try:
        display.display_verify_report(data)
    finally:
        display.console = original
    return console.export_text()


def _report(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "range": {"since": "2024-12-01", "until": "2024-12-31"},
        "stored_count": 31,
        "source_count": 31,
        "matched": 31,
        "missing_from_stk": [],
        "missing_from_source": [],
        "distance_mismatches": [],
        "duration_mismatches": [],
        "low_precision": [],
        "totals": {"stored_km": 160.90218, "source_km": 160.90218, "delta_km": 0.0},
        "clean": True,
    }
    base.update(over)
    return base


def test_clean_report_says_in_sync() -> None:
    out = _render(_report())
    assert "in sync" in out
    assert "matches the source of record" in out
    assert "99.98 mi stored" in out  # the real December total, unrounded


def test_missing_run_is_listed() -> None:
    out = _render(
        _report(
            clean=False,
            missing_from_stk=[
                {"activity_id": "40316850", "date": "2024-12-07", "distance_km": 5.57}
            ],
        )
    )
    assert "drift" in out
    assert "In SmashRun, missing here" in out
    assert "40316850" in out
    assert "2024-12-07" in out


def test_distance_drift_shows_the_delta_in_metres() -> None:
    out = _render(
        _report(
            clean=False,
            distance_mismatches=[
                {
                    "activity_id": "1",
                    "date": "2024-12-01",
                    "stored_km": 5.551,
                    "source_km": 5.55113,
                    "delta_km": 0.00013,
                    "delta_m": 0.13,
                }
            ],
        )
    )
    assert "Distance disagrees" in out
    assert "+0.1 m" in out


def test_low_precision_is_advisory_and_truncated() -> None:
    """Advisory rows do not make the report dirty, and a long list is capped."""
    rows = [
        {"activity_id": str(i), "date": f"2015-01-{i:02d}", "distance_km": 5.551, "decimals": 3}
        for i in range(1, 15)
    ]
    out = _render(_report(low_precision=rows))

    assert "in sync" in out  # still clean
    assert "14 run(s) stored at ≤3 decimals" in out
    assert "and 4 more" in out
