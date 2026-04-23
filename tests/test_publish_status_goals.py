"""Tests for goals block in publish_status status.json payload."""

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.lambdas.publish_status.handler import build_goals_block
from src.shared.supabase_ops import GoalsRepository


@pytest.fixture
def goals_repo() -> GoalsRepository:
    """GoalsRepository with a MagicMock Supabase client."""
    return GoalsRepository(MagicMock())


def _goal_row(goal_km: float | None, progress_km: float | None, text: str = "Test") -> dict:
    return {
        "goal_km": goal_km,
        "progress_km": progress_km,
        "goal_text": text,
        "fetched_at": "2026-04-23T12:00:00+00:00",
    }


def test_goals_block_with_both_goals(goals_repo: GoalsRepository) -> None:
    """Yearly and monthly goals both render correctly in miles."""
    user_id = uuid4()
    source_id = uuid4()
    today = date(2026, 4, 23)

    # Mock get_by_period: first call yearly, second monthly
    goals_repo.get_by_period = MagicMock(  # type: ignore[method-assign]
        side_effect=[
            _goal_row(2500.0, 847.3, "Run 2500 km in 2026"),
            _goal_row(200.0, 89.3, "Run 200 km in April"),
        ]
    )

    block = build_goals_block(user_id, source_id, goals_repo, today)

    assert block["yearly"] is not None
    assert block["yearly"]["goal_mi"] == pytest.approx(1553.4, abs=0.1)
    assert block["yearly"]["progress_mi"] == pytest.approx(526.5, abs=0.1)
    assert block["yearly"]["percent"] == pytest.approx(33.9, abs=0.1)
    assert block["yearly"]["text"] == "Run 2500 km in 2026"

    assert block["monthly"] is not None
    assert block["monthly"]["goal_mi"] == pytest.approx(124.3, abs=0.1)
    assert block["monthly"]["percent"] == pytest.approx(44.65, abs=0.1)


def test_goals_block_missing_rows(goals_repo: GoalsRepository) -> None:
    """No rows stored → both yearly and monthly are None."""
    user_id = uuid4()
    source_id = uuid4()
    today = date(2026, 4, 23)

    goals_repo.get_by_period = MagicMock(return_value=None)  # type: ignore[method-assign]

    block = build_goals_block(user_id, source_id, goals_repo, today)

    assert block == {"yearly": None, "monthly": None}


def test_goals_block_null_goal_km(goals_repo: GoalsRepository) -> None:
    """Placeholder row with goal_km=None (no goal on SmashRun) renders as None."""
    user_id = uuid4()
    source_id = uuid4()
    today = date(2026, 4, 23)

    goals_repo.get_by_period = MagicMock(  # type: ignore[method-assign]
        side_effect=[
            _goal_row(None, None),
            _goal_row(200.0, 50.0, "Monthly"),
        ]
    )

    block = build_goals_block(user_id, source_id, goals_repo, today)

    assert block["yearly"] is None
    assert block["monthly"] is not None
    assert block["monthly"]["goal_mi"] == pytest.approx(124.3, abs=0.1)


def test_goals_block_no_source(goals_repo: GoalsRepository) -> None:
    """No source_id → empty block without hitting the repo."""
    user_id = uuid4()
    today = date(2026, 4, 23)

    goals_repo.get_by_period = MagicMock()  # type: ignore[method-assign]

    block = build_goals_block(user_id, None, goals_repo, today)

    assert block == {"yearly": None, "monthly": None}
    goals_repo.get_by_period.assert_not_called()


def test_goals_block_zero_progress(goals_repo: GoalsRepository) -> None:
    """Zero progress yields percent=0, not error."""
    user_id = uuid4()
    source_id = uuid4()
    today = date(2026, 4, 23)

    goals_repo.get_by_period = MagicMock(  # type: ignore[method-assign]
        side_effect=[_goal_row(2500.0, 0.0), _goal_row(200.0, 0.0)]
    )

    block = build_goals_block(user_id, source_id, goals_repo, today)

    assert block["yearly"]["percent"] == 0.0
    assert block["monthly"]["percent"] == 0.0


def test_goals_block_queries_correct_period(goals_repo: GoalsRepository) -> None:
    """Verifies yearly is queried with month=None and monthly with today.month."""
    user_id = uuid4()
    source_id = uuid4()
    today = date(2026, 7, 15)

    mock_get = MagicMock(return_value=None)
    goals_repo.get_by_period = mock_get  # type: ignore[method-assign]

    build_goals_block(user_id, source_id, goals_repo, today)

    assert mock_get.call_count == 2
    # First call: yearly (month=None)
    assert mock_get.call_args_list[0].args == (user_id, source_id, 2026, None)
    # Second call: monthly (month=7)
    assert mock_get.call_args_list[1].args == (user_id, source_id, 2026, 7)
