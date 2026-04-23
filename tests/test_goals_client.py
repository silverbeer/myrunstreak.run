"""Tests for SmashRun goals endpoint in the API client."""

from unittest.mock import MagicMock

import pytest

from src.shared.models import Goal
from src.shared.smashrun import SmashRunAPIClient


@pytest.fixture
def api_client() -> SmashRunAPIClient:
    """Create API client for testing."""
    return SmashRunAPIClient(access_token="test_access_token")


@pytest.fixture
def sample_goal_response() -> dict[str, object]:
    """Sample /my/goals/{year} response from SmashRun."""
    return {
        "goalText": "Run 2500 km in 2026",
        "goalKilometers": 2500.0,
        "kilometers": 847.3,
    }


def test_get_goal_yearly(api_client: SmashRunAPIClient, sample_goal_response: dict) -> None:
    """Yearly goal request hits /my/goals/{year} and returns a Goal."""
    mock_response = MagicMock()
    mock_response.json.return_value = sample_goal_response
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    api_client._client = mock_client

    goal = api_client.get_goal(2026)

    assert isinstance(goal, Goal)
    assert goal.year == 2026
    assert goal.month is None
    assert goal.is_yearly is True
    assert goal.goal_km == 2500.0
    assert goal.progress_km == 847.3
    assert goal.goal_text == "Run 2500 km in 2026"
    mock_client.get.assert_called_once_with("/my/goals/2026")


def test_get_goal_monthly(api_client: SmashRunAPIClient, sample_goal_response: dict) -> None:
    """Monthly goal request hits /my/goals/{year}/{month}."""
    mock_response = MagicMock()
    mock_response.json.return_value = sample_goal_response
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    api_client._client = mock_client

    goal = api_client.get_goal(2026, 4)

    assert goal is not None
    assert goal.year == 2026
    assert goal.month == 4
    assert goal.is_yearly is False
    mock_client.get.assert_called_once_with("/my/goals/2026/4")


def test_get_goal_returns_none_when_no_goal_set(api_client: SmashRunAPIClient) -> None:
    """SmashRun returns JSON null when no goal is set; client returns None."""
    mock_response = MagicMock()
    mock_response.json.return_value = None
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    api_client._client = mock_client

    goal = api_client.get_goal(2026, 12)

    assert goal is None


def test_get_goal_invalid_month(api_client: SmashRunAPIClient) -> None:
    """Month out of range raises ValueError before any HTTP call."""
    mock_client = MagicMock()
    api_client._client = mock_client

    with pytest.raises(ValueError, match="month must be between 1 and 12"):
        api_client.get_goal(2026, 13)

    mock_client.get.assert_not_called()


def test_goal_mile_conversion() -> None:
    """Goal model exposes miles via property, storing km."""
    goal = Goal(year=2026, goal_km=1609.344, progress_km=804.672)

    assert goal.goal_miles == pytest.approx(1000.0, rel=1e-3)
    assert goal.progress_miles == pytest.approx(500.0, rel=1e-3)
    assert goal.progress_percent == pytest.approx(50.0, rel=1e-3)


def test_goal_progress_percent_without_goal() -> None:
    """progress_percent is None when goal_km is missing."""
    goal = Goal(year=2026, progress_km=100.0)
    assert goal.progress_percent is None


def test_goal_miles_none_when_km_none() -> None:
    """Miles properties return None when km value is None."""
    goal = Goal(year=2026)
    assert goal.goal_miles is None
    assert goal.progress_miles is None
