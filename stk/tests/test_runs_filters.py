"""Tests for the stk runs filter flags, `stk summary`, and `stk goals` (SB-274)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from typer.testing import CliRunner

from cli.commands import runs as runs_cmd
from cli.main import app

runner = CliRunner()


@pytest.fixture()
def captured(monkeypatch):  # type: ignore[no-untyped-def]
    """Capture (endpoint, params) sent by any command; return canned bodies."""
    calls: list[tuple[str, dict[str, Any] | None]] = []

    def fake_request(endpoint: str, params: dict[str, Any] | None = None) -> Any:
        calls.append((endpoint, params))
        if endpoint == "runs":
            return {"total": 0, "offset": 0, "limit": 50, "count": 0, "runs": []}
        if endpoint == "runs/summary":
            return {
                "count": 3,
                "total_km": 10.0,
                "avg_pace_min_per_km": 6.5,
                "overall_avg_pace_min_per_km": 6.2,
            }
        if endpoint == "stats/goals":
            return {"yearly": None, "monthly": None}
        if endpoint == "stats/goals/history":
            return []
        return {}

    monkeypatch.setattr("cli.commands.runs.api.request", fake_request)
    monkeypatch.setattr("cli.commands.stats.api.request", fake_request)
    return calls


# ---------------------------------------------------------------------------
# _filter_params
# ---------------------------------------------------------------------------


def test_filter_params_drops_nones() -> None:
    assert runs_cmd._filter_params(a=1, b=None, c="x") == {"a": 1, "c": "x"}


def test_filter_params_resolves_today() -> None:
    params = runs_cmd._filter_params(on_this_day="today")
    assert params["on_this_day"] == datetime.now().strftime("%m-%d")


def test_filter_params_keeps_explicit_mm_dd() -> None:
    assert runs_cmd._filter_params(on_this_day="07-04") == {"on_this_day": "07-04"}


# ---------------------------------------------------------------------------
# stk runs
# ---------------------------------------------------------------------------


def test_runs_default_params_have_no_none_keys(captured) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["runs", "--json"])
    assert result.exit_code == 0
    endpoint, params = captured[0]
    assert endpoint == "runs"
    assert params == {"offset": 0, "limit": 50, "sort": "date", "order": "desc"}
    assert None not in params.values()


def test_runs_filters_sent_exactly(captured) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(
        app,
        [
            "runs",
            "--on-this-day",
            "07-18",
            "--sort",
            "temperature",
            "--order",
            "asc",
            "--hour-max",
            "5",
            "--json",
        ],
    )
    assert result.exit_code == 0
    _, params = captured[0]
    assert params == {
        "offset": 0,
        "limit": 50,
        "on_this_day": "07-18",
        "hour_max": 5,
        "sort": "temperature",
        "order": "asc",
    }


def test_runs_weather_flag_maps_to_weather_type(captured) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["runs", "--weather", "rain", "--json"])
    assert result.exit_code == 0
    _, params = captured[0]
    assert params["weather_type"] == "rain"
    assert "weather" not in params


def test_runs_on_this_day_today_resolves(captured) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["runs", "--on-this-day", "today", "--json"])
    assert result.exit_code == 0
    _, params = captured[0]
    assert params["on_this_day"] == datetime.now().strftime("%m-%d")


# ---------------------------------------------------------------------------
# stk summary
# ---------------------------------------------------------------------------


def test_summary_no_flags_sends_empty_params(captured) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["summary", "--json"])
    assert result.exit_code == 0
    endpoint, params = captured[0]
    assert endpoint == "runs/summary"
    assert params == {}


def test_summary_sends_only_given_filters(captured) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["summary", "--weather", "rain", "--temp-min", "25", "--json"])
    assert result.exit_code == 0
    _, params = captured[0]
    assert params == {"weather_type": "rain", "temp_min": 25.0}


def test_summary_table_renders(captured) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["summary"])
    assert result.exit_code == 0
    assert "Run Summary" in result.output
    # 6.5 vs 6.2 min/km → slower than overall
    assert "slower" in result.output


# ---------------------------------------------------------------------------
# stk goals
# ---------------------------------------------------------------------------


def test_goals_hits_stats_goals(captured) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["goals", "--json"])
    assert result.exit_code == 0
    endpoint, params = captured[0]
    assert endpoint == "stats/goals"
    assert params is None


def test_goals_history_hits_history_endpoint(captured) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["goals", "--history", "--json"])
    assert result.exit_code == 0
    endpoint, _ = captured[0]
    assert endpoint == "stats/goals/history"


def test_goals_table_renders_no_goal(captured) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["goals"])
    assert result.exit_code == 0
    assert "Distance Goals" in result.output
    assert "no goal set" in result.output


# ---------------------------------------------------------------------------
# UX helpers (SB-276)
# ---------------------------------------------------------------------------


def test_bar_scales_and_floors() -> None:
    from cli import display

    assert display._bar(0, 10) == ""
    assert display._bar(10, 10, width=8) == "▉" * 8
    assert display._bar(0.1, 10, width=8) == "▉"  # non-zero always shows


def test_progress_bar_caps_at_full() -> None:
    from cli import display

    assert display._progress_bar(None, width=8) == "░" * 8
    assert display._progress_bar(150.0, width=8) == "▓" * 8
    half = display._progress_bar(50.0, width=8)
    assert half.count("▓") == 4 and half.count("░") == 4


def test_friendly_date_today_and_fallback() -> None:
    from datetime import date

    from cli import display

    assert "today" in display._friendly_date(date.today().isoformat())
    assert display._friendly_date("garbage") == "garbage"[:10]


def test_recent_table_footer_and_weather(captured) -> None:  # type: ignore[no-untyped-def]
    def fake_request(endpoint: str, params=None):  # type: ignore[no-untyped-def]
        return {
            "count": 2,
            "runs": [
                {
                    "date": "2026-07-18T13:33:00+00:00",
                    "distance_km": 3.0,
                    "duration_minutes": 20.0,
                    "avg_pace_min_per_km": 6.6,
                    "weather": "cloudy",
                    "temperature_celsius": 28.9,
                },
                {
                    "date": "2026-07-17T14:09:00+00:00",
                    "distance_km": 3.3,
                    "duration_minutes": 18.8,
                    "avg_pace_min_per_km": 5.7,
                    "weather": "sunny",
                    "temperature_celsius": None,
                },
            ],
        }

    import pytest as _pytest

    monkeypatch = _pytest.MonkeyPatch()
    monkeypatch.setattr("cli.commands.runs.api.request", fake_request)
    try:
        result = runner.invoke(app, ["recent"])
    finally:
        monkeypatch.undo()
    assert result.exit_code == 0
    assert "2 runs" in result.output  # totals footer
    assert "☁" in result.output  # weather emoji


def test_dashboard_renders_with_all_data(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_request(endpoint: str, params=None):  # type: ignore[no-untyped-def]
        if endpoint == "stats/streaks":
            return {
                "current_streak": 4347,
                "current_streak_km": 30698.5,
                "top_streaks": [{"start_date": "2014-08-24", "is_current": True}],
            }
        if endpoint == "stats/goals":
            return {
                "yearly": {"goal_mi": 1200.0, "progress_mi": 750.0, "percent": 62.5},
                "monthly": {"goal_mi": 125.0, "progress_mi": 64.0, "percent": 51.2},
            }
        if endpoint == "runs/recent":
            return {
                "runs": [
                    {
                        "date": "2026-07-18T13:33:00+00:00",
                        "distance_km": 3.0,
                        "avg_pace_min_per_km": 6.6,
                        "weather": "cloudy",
                        "temperature_celsius": 28.9,
                    }
                ]
            }
        if endpoint == "runs":
            return {"total": 13, "runs": []}
        raise AssertionError(f"unexpected endpoint {endpoint}")

    monkeypatch.setattr("cli.commands.stats.api.request", fake_request)
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "DAY 4,347" in result.output
    assert "vs calendar" in result.output
    assert "13 years" in result.output


def test_dashboard_degrades_when_optional_reads_fail(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import sys as _sys

    def fake_request(endpoint: str, params=None):  # type: ignore[no-untyped-def]
        if endpoint == "stats/streaks":
            return {"current_streak": 100, "current_streak_km": 500.0, "top_streaks": []}
        _sys.exit(1)  # every optional read blows up like api.request would

    monkeypatch.setattr("cli.commands.stats.api.request", fake_request)
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "DAY 100" in result.output
