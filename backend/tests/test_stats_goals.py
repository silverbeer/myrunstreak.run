"""Tests for the GET /stats/goals route."""

from __future__ import annotations

import importlib
from datetime import date
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest


@pytest.fixture(autouse=True)
def _disable_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make @cached a no-op so each test exercises the real fetch path
    without needing a Redis (or worrying about cross-test bleed)."""
    monkeypatch.setenv("CACHE_ENABLED", "false")
    import backend.cache
    import backend.config
    import backend.routes.stats

    importlib.reload(backend.config)
    importlib.reload(backend.cache)
    importlib.reload(backend.routes.stats)


@pytest.fixture
def user_id() -> str:
    return str(uuid4())


async def _call(user_id: str) -> dict:
    """Invoke the cached _goals helper directly so tests don't require a
    full FastAPI ASGI client."""
    from backend.routes.stats import _goals

    return await _goals(UUID(user_id))


@pytest.mark.asyncio
async def test_goals_returns_yearly_and_monthly(user_id: str) -> None:
    """Both periods stored → both rendered, fields in miles."""
    source_id = uuid4()
    token_repo = MagicMock()
    token_repo.get_source_id_for_user.return_value = source_id

    goals_repo = MagicMock()
    goals_repo.get_by_period.side_effect = [
        {"goal_km": 1931.2, "progress_km": 762.0, "goal_text": "1200 mi", "fetched_at": "Z"},
        {"goal_km": 201.2, "progress_km": 62.5, "goal_text": "125 mi", "fetched_at": "Z"},
    ]

    with (
        patch("backend.routes.stats.get_supabase_client"),
        patch("backend.routes.stats.TokenRepository", return_value=token_repo),
        patch("backend.routes.stats.GoalsRepository", return_value=goals_repo),
    ):
        result = await _call(user_id)

    assert result["yearly"]["goal_mi"] == pytest.approx(1200.0, abs=0.2)
    assert result["yearly"]["text"] == "1200 mi"
    assert result["monthly"]["goal_mi"] == pytest.approx(125.0, abs=0.2)
    assert result["monthly"]["text"] == "125 mi"


@pytest.mark.asyncio
async def test_goals_returns_nulls_when_no_source(user_id: str) -> None:
    """User has no SmashRun source linked → both periods null, no goals query."""
    token_repo = MagicMock()
    token_repo.get_source_id_for_user.return_value = None

    goals_repo = MagicMock()

    with (
        patch("backend.routes.stats.get_supabase_client"),
        patch("backend.routes.stats.TokenRepository", return_value=token_repo),
        patch("backend.routes.stats.GoalsRepository", return_value=goals_repo),
    ):
        result = await _call(user_id)

    assert result == {"yearly": None, "monthly": None}
    goals_repo.get_by_period.assert_not_called()


@pytest.mark.asyncio
async def test_goals_returns_nulls_when_periods_unfetched(user_id: str) -> None:
    """User has source but no goals stored yet → both null."""
    source_id = uuid4()
    token_repo = MagicMock()
    token_repo.get_source_id_for_user.return_value = source_id

    goals_repo = MagicMock()
    goals_repo.get_by_period.return_value = None

    with (
        patch("backend.routes.stats.get_supabase_client"),
        patch("backend.routes.stats.TokenRepository", return_value=token_repo),
        patch("backend.routes.stats.GoalsRepository", return_value=goals_repo),
    ):
        result = await _call(user_id)

    assert result == {"yearly": None, "monthly": None}


@pytest.mark.asyncio
async def test_goals_uses_current_year_month_in_ny_tz(user_id: str) -> None:
    """build_goals_block must be called with today() in America/New_York,
    so the 'current month' is consistent with publish_status."""
    source_id = uuid4()
    token_repo = MagicMock()
    token_repo.get_source_id_for_user.return_value = source_id

    goals_repo = MagicMock()
    goals_repo.get_by_period.return_value = None

    fixed_date = date(2026, 5, 9)
    with (
        patch("backend.routes.stats.get_supabase_client"),
        patch("backend.routes.stats.TokenRepository", return_value=token_repo),
        patch("backend.routes.stats.GoalsRepository", return_value=goals_repo),
        patch("backend.routes.stats._today_local", return_value=fixed_date),
    ):
        await _call(user_id)

    yearly_call = goals_repo.get_by_period.call_args_list[0]
    monthly_call = goals_repo.get_by_period.call_args_list[1]
    assert yearly_call.args[2] == 2026 and yearly_call.args[3] is None
    assert monthly_call.args[2] == 2026 and monthly_call.args[3] == 5
