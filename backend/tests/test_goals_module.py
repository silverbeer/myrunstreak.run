"""Tests for backend.goals — shared goals-block presentation."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from backend.goals import build_goals_block, km_to_miles, render_goal


def test_km_to_miles() -> None:
    assert km_to_miles(1.609344) == pytest.approx(1.0, abs=0.001)


def test_render_goal_returns_none_for_missing_row() -> None:
    assert render_goal(None) is None


def test_render_goal_returns_none_when_goal_km_is_null() -> None:
    """Placeholder 'absent' row from GoalsRepository.mark_absent."""
    row = {"goal_km": None, "progress_km": None, "fetched_at": "2026-05-09T19:00:00Z"}
    assert render_goal(row) is None


def test_render_goal_full_payload() -> None:
    row = {
        "goal_km": 1931.2,
        "progress_km": 762.0,
        "goal_text": "1200 mi this year",
        "fetched_at": "2026-05-09T19:31:44Z",
    }
    result = render_goal(row)
    assert result is not None
    assert result["goal_mi"] == pytest.approx(1200.0, abs=0.2)
    assert result["progress_mi"] == pytest.approx(473.5, abs=0.2)
    assert result["percent"] == pytest.approx(39.5, abs=0.2)
    assert result["text"] == "1200 mi this year"
    assert result["fetched_at"] == "2026-05-09T19:31:44Z"


def test_render_goal_zero_goal_km_yields_null_percent() -> None:
    """Belt-and-suspenders — the schema CHECK forbids goal_km <= 0,
    but if a 0 ever leaked through we shouldn't divide by zero."""
    row = {"goal_km": 0.0, "progress_km": 0.0, "fetched_at": "2026-05-09T19:00:00Z"}
    # goal_km == 0 means no goal worth showing — render_goal treats it as
    # absent only when goal_km is *None*; with 0.0 it returns a row but
    # percent = None (not a divide-by-zero crash).
    result = render_goal(row)
    assert result is not None
    assert result["percent"] is None


def test_build_goals_block_no_source_returns_nulls() -> None:
    repo = MagicMock()
    result = build_goals_block(uuid4(), None, repo, date(2026, 5, 9))

    assert result == {"yearly": None, "monthly": None}
    repo.get_by_period.assert_not_called()


def test_build_goals_block_queries_yearly_and_monthly() -> None:
    user_id, source_id = uuid4(), uuid4()
    repo = MagicMock()
    repo.get_by_period.side_effect = [
        {"goal_km": 1931.2, "progress_km": 762.0, "goal_text": "year", "fetched_at": "Z"},
        {"goal_km": 201.2, "progress_km": 62.5, "goal_text": "month", "fetched_at": "Z"},
    ]

    result = build_goals_block(user_id, source_id, repo, date(2026, 5, 9))

    assert repo.get_by_period.call_args_list[0].args == (user_id, source_id, 2026, None)
    assert repo.get_by_period.call_args_list[1].args == (user_id, source_id, 2026, 5)
    assert result["yearly"]["text"] == "year"
    assert result["monthly"]["text"] == "month"


def test_build_goals_block_handles_one_period_missing() -> None:
    """One period stored, the other absent — render only the populated one."""
    user_id, source_id = uuid4(), uuid4()
    repo = MagicMock()
    repo.get_by_period.side_effect = [
        None,  # no yearly row
        {"goal_km": 201.2, "progress_km": 62.5, "fetched_at": "Z"},
    ]

    result = build_goals_block(user_id, source_id, repo, date(2026, 5, 9))

    assert result["yearly"] is None
    assert result["monthly"] is not None


def test_render_goal_override_uses_runs_not_stale_mirror() -> None:
    """progress_km_override (from synced runs) wins over the mirror's progress_km."""
    row = {"goal_km": 209.2, "progress_km": 112.3, "goal_text": "month", "fetched_at": "Z"}
    result = render_goal(row, progress_km_override=125.2)
    assert result is not None
    assert result["progress_mi"] == pytest.approx(km_to_miles(125.2), abs=0.1)  # not 112.3


def test_build_goals_block_progress_from_run_stats() -> None:
    """With a runs_repo, progress comes from the accurate year/month-to-date
    aggregates — not SmashRun's stale cached goal-progress field."""
    user_id, source_id = uuid4(), uuid4()
    repo = MagicMock()
    repo.get_by_period.side_effect = [
        {"goal_km": 1931.2, "progress_km": 950.0, "goal_text": "year", "fetched_at": "Z"},
        {"goal_km": 209.2, "progress_km": 112.3, "goal_text": "month", "fetched_at": "Z"},
    ]
    runs_repo = MagicMock()
    runs_repo.get_user_running_stats.return_value = {
        "year_to_date_distance_km": 1026.5,
        "month_to_date_distance_km": 125.2,
    }

    result = build_goals_block(user_id, source_id, repo, date(2026, 6, 18), runs_repo)

    assert result["yearly"]["progress_mi"] == pytest.approx(km_to_miles(1026.5), abs=0.1)
    assert result["monthly"]["progress_mi"] == pytest.approx(km_to_miles(125.2), abs=0.1)
