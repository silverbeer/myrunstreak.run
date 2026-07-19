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
