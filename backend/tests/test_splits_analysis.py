"""Tests for backend.splits_analysis — pure per-mile split math."""

from __future__ import annotations

from backend.splits_analysis import (
    KM_TO_MILES,
    analyze_run,
    format_pace,
    per_mile_splits,
    summarize,
)

MI_KM = 1.0 / KM_TO_MILES  # one mile in km


def _rows(paces_sec_per_mile: list[float]) -> list[dict]:
    """Build cumulative split rows from a list of per-mile durations (seconds)."""
    rows = []
    cum_km = 0.0
    cum_s = 0.0
    for i, secs in enumerate(paces_sec_per_mile, start=1):
        cum_km += MI_KM
        cum_s += secs
        rows.append(
            {"split_number": i, "cumulative_distance_km": cum_km, "cumulative_seconds": cum_s}
        )
    return rows


def test_per_mile_splits_differences_cumulative() -> None:
    splits = per_mile_splits(_rows([480.0, 470.0]))  # 8:00, 7:50
    assert len(splits) == 2
    assert splits[0]["pace_min_per_mi"] == 8.0
    assert splits[1]["pace_min_per_mi"] == round(470 / 60, 2)


def test_negative_split_detected() -> None:
    # second half faster than first → negative split
    a = analyze_run(_rows([540.0, 540.0, 480.0, 480.0]))  # 9:00,9:00,8:00,8:00
    assert a is not None
    assert a["negative_split"] is True
    assert a["fade_pct"] < 0  # sped up
    assert a["first_mile_pace"] == 9.0
    assert a["last_mile_pace"] == 8.0


def test_positive_split_is_not_negative() -> None:
    a = analyze_run(_rows([480.0, 480.0, 540.0, 540.0]))  # faded
    assert a is not None
    assert a["negative_split"] is False
    assert a["fade_pct"] > 0


def test_single_split_returns_none() -> None:
    assert analyze_run(_rows([480.0])) is None


def test_summarize_rate_and_averages() -> None:
    neg = analyze_run(_rows([540.0, 480.0]))
    pos = analyze_run(_rows([480.0, 540.0]))
    out = summarize([neg, pos, None])
    assert out["runs_analyzed"] == 2
    assert out["negative_split_rate_pct"] == 50.0


def test_format_pace() -> None:
    assert format_pace(9.5) == "9:30 /mi"
    assert format_pace(7.99) == "7:59 /mi"
    assert format_pace(None) is None
