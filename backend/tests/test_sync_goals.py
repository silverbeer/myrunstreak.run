"""Tests for goal-refresh wiring in backend/routes/sync.py."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from backend.config import Settings
from backend.routes.sync import run_user_sync, sync_current_goals
from src.shared.models import Goal


def _settings() -> Settings:
    return Settings(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test-anon-key",
        supabase_service_role_key="test-service-key",
        supabase_jwt_secret="test-jwt-secret-needs-to-be-long-enough-for-hs256",
        goal_yearly_staleness_days=14,
        goal_monthly_staleness_days=3,
    )


def test_stale_goal_triggers_fetch_and_upsert() -> None:
    """Stale (here: missing) rows → fetch from SmashRun and upsert each period."""
    user_id, source_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    api = MagicMock()
    fetched_yearly = Goal(year=now.year, goal_km=1000.0, progress_km=500.0)
    fetched_monthly = Goal(year=now.year, month=now.month, goal_km=80.0, progress_km=20.0)
    api.get_goal.side_effect = [fetched_yearly, fetched_monthly]

    repo = MagicMock()
    repo.get_by_period.return_value = None  # both periods missing
    repo.is_stale.return_value = True

    sync_current_goals(user_id, source_id, api, repo, _settings())

    assert api.get_goal.call_count == 2
    assert repo.upsert.call_args_list == [
        ((user_id, source_id, fetched_yearly),),
        ((user_id, source_id, fetched_monthly),),
    ]
    repo.mark_absent.assert_not_called()


def test_fresh_row_skips_api_call() -> None:
    """Row inside TTL is fresh; sync must not call SmashRun."""
    user_id, source_id = uuid4(), uuid4()
    api = MagicMock()
    repo = MagicMock()
    repo.get_by_period.return_value = {"fetched_at": datetime.now(UTC).isoformat()}
    repo.is_stale.return_value = False

    sync_current_goals(user_id, source_id, api, repo, _settings())

    api.get_goal.assert_not_called()
    repo.upsert.assert_not_called()
    repo.mark_absent.assert_not_called()


def test_force_refetches_even_when_fresh() -> None:
    """force=True (a user 'Sync now') ignores the TTL and re-fetches anyway,
    so a goal set after an 'absent' mark shows up immediately (SB-222)."""
    user_id, source_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    api = MagicMock()
    api.get_goal.side_effect = [
        Goal(year=now.year, goal_km=1000.0, progress_km=500.0),
        Goal(year=now.year, month=now.month, goal_km=80.0, progress_km=20.0),
    ]
    repo = MagicMock()
    repo.get_by_period.return_value = {"fetched_at": now.isoformat()}
    repo.is_stale.return_value = False  # fresh — would normally skip

    sync_current_goals(user_id, source_id, api, repo, _settings(), force=True)

    assert api.get_goal.call_count == 2  # both periods fetched despite freshness
    assert repo.upsert.call_count == 2


def test_smashrun_returns_none_marks_absent() -> None:
    """SmashRun reports no goal set → mark_absent so we don't re-fetch."""
    user_id, source_id = uuid4(), uuid4()
    api = MagicMock()
    api.get_goal.return_value = None  # no goal set on either period

    repo = MagicMock()
    repo.get_by_period.return_value = None
    repo.is_stale.return_value = True

    sync_current_goals(user_id, source_id, api, repo, _settings())

    assert repo.mark_absent.call_count == 2  # yearly + monthly
    repo.upsert.assert_not_called()


def test_run_user_sync_swallows_goal_failure() -> None:
    """A goal-sync exception must not fail the whole sync."""
    user_id = uuid4()
    source_id = uuid4()

    token_repo = MagicMock()
    token_repo.get_source_id_for_user.return_value = source_id
    token_repo.get_user_tokens.return_value = {
        "access_token": "tok",
        "refresh_token": "ref",
    }
    token_repo.is_token_expired.return_value = False

    api = MagicMock()
    api.get_all_activities_since.return_value = []
    api_ctx = MagicMock()
    api_ctx.__enter__ = MagicMock(return_value=api)
    api_ctx.__exit__ = MagicMock(return_value=False)

    with (
        patch("backend.routes.sync.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.sync.RunsRepository"),
        patch("backend.routes.sync.TokenRepository", return_value=token_repo),
        patch("backend.routes.sync.GoalsRepository"),
        patch("backend.routes.sync.SmashRunAPIClient", return_value=api_ctx),
        patch(
            "backend.routes.sync.sync_current_goals",
            side_effect=RuntimeError("smashrun on fire"),
        ),
    ):
        result = run_user_sync(user_id, since=None, until=None, full=False)

    assert result["runs_synced"] == 0
    assert result["message"] == "Sync completed"


def test_run_user_sync_threads_force_goals() -> None:
    """run_user_sync(force_goals=True) passes force=True to sync_current_goals;
    the default leaves it False (cron path keeps the TTL)."""
    user_id, source_id = uuid4(), uuid4()

    token_repo = MagicMock()
    token_repo.get_source_id_for_user.return_value = source_id
    token_repo.get_user_tokens.return_value = {"access_token": "tok", "refresh_token": "ref"}
    token_repo.is_token_expired.return_value = False

    api = MagicMock()
    api.get_all_activities_since.return_value = []
    api_ctx = MagicMock()
    api_ctx.__enter__ = MagicMock(return_value=api)
    api_ctx.__exit__ = MagicMock(return_value=False)

    for force_goals, expected in [(True, True), (False, False)]:
        goal_sync = MagicMock()
        with (
            patch("backend.routes.sync.get_supabase_client", return_value=MagicMock()),
            patch("backend.routes.sync.RunsRepository"),
            patch("backend.routes.sync.TokenRepository", return_value=token_repo),
            patch("backend.routes.sync.GoalsRepository"),
            patch("backend.routes.sync.SmashRunAPIClient", return_value=api_ctx),
            patch("backend.routes.sync.sync_current_goals", goal_sync),
        ):
            run_user_sync(user_id, force_goals=force_goals)
        assert goal_sync.call_args.kwargs["force"] is expected


def test_settings_drive_per_period_ttl() -> None:
    """Yearly + monthly periods consult is_stale with their respective TTLs."""
    user_id, source_id = uuid4(), uuid4()
    settings = _settings()
    api = MagicMock()
    api.get_goal.return_value = None
    repo = MagicMock()
    repo.get_by_period.return_value = None
    repo.is_stale.return_value = True

    sync_current_goals(user_id, source_id, api, repo, settings)

    ttl_args = [call.args[1] for call in repo.is_stale.call_args_list]
    assert timedelta(days=settings.goal_yearly_staleness_days) in ttl_args
    assert timedelta(days=settings.goal_monthly_staleness_days) in ttl_args


def test_run_user_sync_recalculates_user_stats() -> None:
    """sync must call RunsRepository.recalculate_user_stats so the
    user_running_stats aggregation row reflects the runs just upserted."""
    user_id = uuid4()
    source_id = uuid4()

    token_repo = MagicMock()
    token_repo.get_source_id_for_user.return_value = source_id
    token_repo.get_user_tokens.return_value = {
        "access_token": "tok",
        "refresh_token": "ref",
    }
    token_repo.is_token_expired.return_value = False

    runs_repo_instance = MagicMock()

    api = MagicMock()
    api.get_all_activities_since.return_value = []
    api_ctx = MagicMock()
    api_ctx.__enter__ = MagicMock(return_value=api)
    api_ctx.__exit__ = MagicMock(return_value=False)

    with (
        patch("backend.routes.sync.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.sync.RunsRepository", return_value=runs_repo_instance),
        patch("backend.routes.sync.TokenRepository", return_value=token_repo),
        patch("backend.routes.sync.GoalsRepository"),
        patch("backend.routes.sync.SmashRunAPIClient", return_value=api_ctx),
        patch("backend.routes.sync.sync_current_goals"),
    ):
        run_user_sync(user_id)

    runs_repo_instance.recalculate_user_stats.assert_called_once_with(
        user_id, timezone="America/New_York"
    )


def test_run_user_sync_swallows_recalc_failure() -> None:
    """A recalculate_user_stats exception must not fail the whole sync."""
    user_id = uuid4()
    source_id = uuid4()

    token_repo = MagicMock()
    token_repo.get_source_id_for_user.return_value = source_id
    token_repo.get_user_tokens.return_value = {
        "access_token": "tok",
        "refresh_token": "ref",
    }
    token_repo.is_token_expired.return_value = False

    runs_repo_instance = MagicMock()
    runs_repo_instance.recalculate_user_stats.side_effect = RuntimeError("supabase down")

    api = MagicMock()
    api.get_all_activities_since.return_value = []
    api_ctx = MagicMock()
    api_ctx.__enter__ = MagicMock(return_value=api)
    api_ctx.__exit__ = MagicMock(return_value=False)

    with (
        patch("backend.routes.sync.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.sync.RunsRepository", return_value=runs_repo_instance),
        patch("backend.routes.sync.TokenRepository", return_value=token_repo),
        patch("backend.routes.sync.GoalsRepository"),
        patch("backend.routes.sync.SmashRunAPIClient", return_value=api_ctx),
        patch("backend.routes.sync.sync_current_goals"),
    ):
        result = run_user_sync(user_id)

    assert result["message"] == "Sync completed"
