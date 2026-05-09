"""Tests for backend.jobs.publish_status."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from backend.jobs.publish_status import (
    build_goals_block,
    build_status_data,
    format_streak_duration,
    get_gcs_credentials,
    km_to_miles,
    resolve_user_and_source,
    upload_to_gcs,
)

# ---------------------------------------------------------------------------
# format_streak_duration
# ---------------------------------------------------------------------------


def test_format_streak_duration_returns_none_when_no_start() -> None:
    assert format_streak_duration(None, date(2026, 5, 9)) is None


def test_format_streak_duration_full_form() -> None:
    assert format_streak_duration("2014-08-23", date(2026, 5, 9)) == "11 years, 8 months and 16 days"


def test_format_streak_duration_singular_units() -> None:
    assert format_streak_duration("2025-04-08", date(2026, 5, 9)) == "1 year, 1 month and 1 day"


def test_format_streak_duration_only_days() -> None:
    assert format_streak_duration("2026-05-04", date(2026, 5, 9)) == "5 days"


def test_format_streak_duration_zero_days_same_date() -> None:
    """Same start + today should still render '0 days' (not blank)."""
    assert format_streak_duration("2026-05-09", date(2026, 5, 9)) == "0 days"


# ---------------------------------------------------------------------------
# km_to_miles
# ---------------------------------------------------------------------------


def test_km_to_miles_round_trip() -> None:
    assert km_to_miles(1.609344) == pytest.approx(1.0, abs=0.001)


# ---------------------------------------------------------------------------
# build_goals_block
# ---------------------------------------------------------------------------


def test_build_goals_block_no_source_returns_nulls() -> None:
    repo = MagicMock()
    result = build_goals_block(uuid4(), None, repo, date(2026, 5, 9))

    assert result == {"yearly": None, "monthly": None}
    repo.get_by_period.assert_not_called()


def test_build_goals_block_renders_yearly_and_monthly() -> None:
    user_id, source_id = uuid4(), uuid4()
    repo = MagicMock()
    repo.get_by_period.side_effect = [
        {
            "goal_km": 1931.0,  # ~1200 mi
            "progress_km": 721.4,  # ~448.1 mi
            "goal_text": "1200 mi this year",
            "fetched_at": "2026-05-09T12:00:00Z",
        },
        {
            "goal_km": 201.2,  # ~125 mi
            "progress_km": 21.7,  # ~13.5 mi
            "goal_text": "125 mi this month",
            "fetched_at": "2026-05-09T12:00:00Z",
        },
    ]

    result = build_goals_block(user_id, source_id, repo, date(2026, 5, 9))

    assert result["yearly"]["goal_mi"] == pytest.approx(1200.0, abs=0.2)
    assert result["yearly"]["progress_mi"] == pytest.approx(448.1, abs=0.2)
    assert result["yearly"]["percent"] == pytest.approx(37.4, abs=0.5)
    assert result["yearly"]["text"] == "1200 mi this year"

    assert result["monthly"]["goal_mi"] == pytest.approx(125.0, abs=0.2)
    assert result["monthly"]["progress_mi"] == pytest.approx(13.5, abs=0.2)
    assert result["monthly"]["percent"] == pytest.approx(10.8, abs=0.5)


def test_build_goals_block_null_goal_km_renders_as_none() -> None:
    """A row exists but goal_km is null (no goal set on SmashRun) → None."""
    user_id, source_id = uuid4(), uuid4()
    repo = MagicMock()
    repo.get_by_period.side_effect = [
        {"goal_km": None, "progress_km": None, "fetched_at": "2026-05-09T12:00:00Z"},
        None,  # not even a row stored for monthly
    ]

    result = build_goals_block(user_id, source_id, repo, date(2026, 5, 9))

    assert result == {"yearly": None, "monthly": None}


# ---------------------------------------------------------------------------
# build_status_data
# ---------------------------------------------------------------------------


def _runs_repo_with(stats: dict | None, recent_runs: list[dict]) -> MagicMock:
    repo = MagicMock()
    repo.get_runs_by_date_range.return_value = recent_runs
    repo.get_user_running_stats.return_value = stats
    return repo


def test_build_status_data_full_payload_shape() -> None:
    """Top-level keys + types match the StreakData interface qualityplaybook.dev expects."""
    user_id, source_id = uuid4(), uuid4()
    today_iso = "2026-05-09"
    runs_repo = _runs_repo_with(
        stats={
            "current_streak_days": 4272,
            "current_streak_start": "2014-08-23",
            "current_streak_distance_km": 30210.0,
            "month_to_date_distance_km": 30.5,
            "year_to_date_distance_km": 730.0,
        },
        recent_runs=[
            {"start_date": today_iso, "distance_km": 6.5, "duration_seconds": 2400},
            {"start_date": "2026-05-08", "distance_km": 5.0, "duration_seconds": 2100},
        ],
    )
    goals_repo = MagicMock()
    goals_repo.get_by_period.return_value = None  # no goals stored

    with patch(
        "backend.jobs.publish_status.datetime"
    ) as mock_dt:
        mock_dt.now.return_value.date.return_value = date(2026, 5, 9)
        # Let datetime.now(UTC).isoformat() produce something deterministic
        mock_dt.now.return_value.isoformat.return_value = "2026-05-09T14:00:00+00:00"
        result = build_status_data(user_id, runs_repo, goals_repo, source_id)

    # Top-level shape
    assert set(result.keys()) >= {
        "updated_at",
        "ran_today",
        "streak",
        "last_run",
        "last_7_days",
        "month_total_mi",
        "year_total_mi",
        "goals",
    }

    # ran_today flag
    assert result["ran_today"] is True

    # Streak block
    assert result["streak"]["current_days"] == 4272
    assert result["streak"]["started"] == "2014-08-23"
    assert result["streak"]["total_mi"] == round(km_to_miles(30210.0), 1)
    assert "year" in result["streak"]["duration"]  # "11 years, ..."

    # Last run + last 7 days are in miles
    assert result["last_run"]["date"] == today_iso
    assert result["last_run"]["distance_mi"] == pytest.approx(km_to_miles(6.5), abs=0.01)
    assert result["last_run"]["duration_min"] == 40.0
    assert len(result["last_7_days"]) == 2

    # Period totals in miles
    assert result["month_total_mi"] == round(km_to_miles(30.5), 1)
    assert result["year_total_mi"] == round(km_to_miles(730.0), 1)

    # Goals are null when nothing stored
    assert result["goals"] == {"yearly": None, "monthly": None}


def test_build_status_data_ran_today_false_when_no_run_today() -> None:
    user_id, source_id = uuid4(), uuid4()
    runs_repo = _runs_repo_with(
        stats={"current_streak_days": 0},
        recent_runs=[
            {"start_date": "2026-05-08", "distance_km": 5.0, "duration_seconds": 2100},
        ],
    )
    goals_repo = MagicMock()
    goals_repo.get_by_period.return_value = None

    with patch("backend.jobs.publish_status.datetime") as mock_dt:
        mock_dt.now.return_value.date.return_value = date(2026, 5, 9)
        mock_dt.now.return_value.isoformat.return_value = "2026-05-09T14:00:00+00:00"
        result = build_status_data(user_id, runs_repo, goals_repo, source_id)

    assert result["ran_today"] is False


def test_build_status_data_falls_back_to_recalculate_when_stats_missing() -> None:
    """Missing user_running_stats row triggers recalculate_user_stats."""
    user_id, source_id = uuid4(), uuid4()
    runs_repo = MagicMock()
    runs_repo.get_runs_by_date_range.return_value = []
    runs_repo.get_user_running_stats.return_value = None
    runs_repo.recalculate_user_stats.return_value = {
        "current_streak_days": 1,
        "current_streak_start": "2026-05-09",
    }

    goals_repo = MagicMock()
    goals_repo.get_by_period.return_value = None

    with patch("backend.jobs.publish_status.datetime") as mock_dt:
        mock_dt.now.return_value.date.return_value = date(2026, 5, 9)
        mock_dt.now.return_value.isoformat.return_value = "2026-05-09T14:00:00+00:00"
        result = build_status_data(user_id, runs_repo, goals_repo, source_id)

    runs_repo.recalculate_user_stats.assert_called_once_with(
        user_id, timezone="America/New_York"
    )
    assert result["streak"]["current_days"] == 1


def test_build_status_data_uses_defaults_when_recalc_explodes() -> None:
    """Even if recalculate also fails, we publish a sensible empty-ish payload."""
    user_id, source_id = uuid4(), uuid4()
    runs_repo = MagicMock()
    runs_repo.get_runs_by_date_range.return_value = []
    runs_repo.get_user_running_stats.return_value = None
    runs_repo.recalculate_user_stats.side_effect = RuntimeError("supabase down")

    goals_repo = MagicMock()
    goals_repo.get_by_period.return_value = None

    with patch("backend.jobs.publish_status.datetime") as mock_dt:
        mock_dt.now.return_value.date.return_value = date(2026, 5, 9)
        mock_dt.now.return_value.isoformat.return_value = "2026-05-09T14:00:00+00:00"
        result = build_status_data(user_id, runs_repo, goals_repo, source_id)

    assert result["streak"]["current_days"] == 0
    assert result["last_run"] is None
    assert result["last_7_days"] == []


# ---------------------------------------------------------------------------
# resolve_user_and_source
# ---------------------------------------------------------------------------


def test_resolve_user_and_source_returns_first_active() -> None:
    user_id, src_id = str(uuid4()), str(uuid4())
    users_repo = MagicMock()
    users_repo.get_all_active_sources.return_value = [
        {"user_id": user_id, "id": src_id},
    ]

    got_user, got_src = resolve_user_and_source(users_repo)

    assert str(got_user) == user_id
    assert str(got_src) == src_id
    users_repo.get_all_active_sources.assert_called_once_with(source_type="smashrun")


def test_resolve_user_and_source_raises_on_no_sources() -> None:
    users_repo = MagicMock()
    users_repo.get_all_active_sources.return_value = []

    with pytest.raises(RuntimeError, match="No active SmashRun sources"):
        resolve_user_and_source(users_repo)


# ---------------------------------------------------------------------------
# get_gcs_credentials
# ---------------------------------------------------------------------------


def test_get_gcs_credentials_parses_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"type": "service_account", "project_id": "missing-table"}
    monkeypatch.setenv("GCS_SERVICE_ACCOUNT_JSON", json.dumps(payload))

    assert get_gcs_credentials() == payload


def test_get_gcs_credentials_raises_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GCS_SERVICE_ACCOUNT_JSON", raising=False)

    with pytest.raises(RuntimeError, match="GCS_SERVICE_ACCOUNT_JSON"):
        get_gcs_credentials()


# ---------------------------------------------------------------------------
# upload_to_gcs (mocked GCS client)
# ---------------------------------------------------------------------------


def test_upload_to_gcs_writes_payload_with_cache_control(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "GCS_SERVICE_ACCOUNT_JSON",
        json.dumps({"type": "service_account", "project_id": "missing-table"}),
    )

    blob = MagicMock()
    bucket = MagicMock()
    bucket.blob.return_value = blob
    client = MagicMock()
    client.bucket.return_value = bucket

    with (
        patch("backend.jobs.publish_status.service_account.Credentials.from_service_account_info"),
        patch("backend.jobs.publish_status.storage.Client", return_value=client),
    ):
        url = upload_to_gcs({"ran_today": True})

    assert url == "https://storage.googleapis.com/myrunstreak-public/status.json"
    client.bucket.assert_called_once_with("myrunstreak-public")
    bucket.blob.assert_called_once_with("status.json")
    assert blob.cache_control == "public, max-age=300"
    blob.upload_from_string.assert_called_once()
    args, kwargs = blob.upload_from_string.call_args
    assert kwargs["content_type"] == "application/json"
    # Body must be valid JSON containing the input fields
    body = json.loads(args[0])
    assert body["ran_today"] is True
