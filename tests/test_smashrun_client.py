"""Tests for SmashRun API client."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.shared.smashrun import SmashRunAPIClient


@pytest.fixture
def api_client():
    """Create API client for testing."""
    return SmashRunAPIClient(access_token="test_access_token")


@pytest.fixture
def sample_activity():
    """Sample activity data from SmashRun API."""
    return {
        "activityId": "12345",
        "startDateTimeLocal": "2024-10-30T08:00:00-04:00",
        "distance": 10.0,
        "duration": 3600,
        "cadenceAverage": 170.0,
        "heartRateAverage": 145.0,
        "terrain": "road",
        "weatherType": "clear",
        "temperature": 15,
    }


def test_api_client_initialization(api_client):
    """Test API client initialization."""
    assert api_client.access_token == "test_access_token"
    assert api_client._client is None


def test_context_manager():
    """Test using API client as context manager."""
    client = SmashRunAPIClient(access_token="test_token")

    assert client._client is None

    with client as c:
        assert c._client is not None
        assert isinstance(c._client.headers["Authorization"], str)
        assert "Bearer test_token" in c._client.headers["Authorization"]

    assert client._client is None


def test_client_property_outside_context_manager(api_client):
    """Test that accessing client property outside context manager raises error."""
    with pytest.raises(RuntimeError, match="must be used as a context manager"):
        _ = api_client.client


@patch("httpx.Client")
def test_get_activities_basic(mock_client_class, api_client, sample_activity):
    """Test fetching activities with basic parameters."""
    # Mock response
    mock_response = MagicMock()
    mock_response.json.return_value = [sample_activity]
    mock_response.raise_for_status = MagicMock()

    # Mock client
    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    api_client._client = mock_client

    # Fetch activities
    activities = api_client.get_activities(page=0, count=10)

    # Verify
    assert len(activities) == 1
    assert activities[0]["activityId"] == "12345"
    assert activities[0]["distance"] == 10.0

    # Verify GET was called correctly
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert call_args[0][0] == "/my/activities/search"
    assert call_args[1]["params"]["page"] == 0
    assert call_args[1]["params"]["count"] == 10


@patch("httpx.Client")
def test_get_activities_with_date_filter(mock_client_class, api_client, sample_activity):
    """Test fetching activities with date filtering (client-side filtering)."""
    # Create activities both inside and outside the date range
    in_range_activity = {
        **sample_activity,
        "activityId": "1",
        "startDateTimeLocal": "2024-10-15T08:00:00-04:00",
    }
    before_range_activity = {
        **sample_activity,
        "activityId": "2",
        "startDateTimeLocal": "2024-09-15T08:00:00-04:00",
    }
    after_range_activity = {
        **sample_activity,
        "activityId": "3",
        "startDateTimeLocal": "2024-11-15T08:00:00-05:00",
    }

    mock_response = MagicMock()
    mock_response.json.return_value = [in_range_activity, before_range_activity, after_range_activity]
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    api_client._client = mock_client

    # Fetch activities with date filter (client-side filtering)
    since_date = date(2024, 10, 1)
    until_date = date(2024, 10, 31)
    activities = api_client.get_activities(page=0, count=50, since=since_date, until=until_date)

    # Verify that only in-range activity is returned
    assert len(activities) == 1
    assert activities[0]["activityId"] == "1"

    # Verify API call doesn't include since/until (filtering is client-side)
    call_args = mock_client.get.call_args
    assert "since" not in call_args[1]["params"]
    assert "until" not in call_args[1]["params"]


@patch("httpx.Client")
def test_get_activity_by_id(mock_client_class, api_client, sample_activity):
    """Test fetching specific activity by ID."""
    mock_response = MagicMock()
    mock_response.json.return_value = sample_activity
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    api_client._client = mock_client

    # Fetch activity
    activity = api_client.get_activity_by_id("12345")

    # Verify
    assert activity["activityId"] == "12345"
    mock_client.get.assert_called_once_with("/my/activities/12345")


@patch("httpx.Client")
def test_get_latest_activity(mock_client_class, api_client, sample_activity):
    """Test fetching the most recent activity."""
    mock_response = MagicMock()
    mock_response.json.return_value = [sample_activity]
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    api_client._client = mock_client

    # Fetch latest
    activity = api_client.get_latest_activity()

    # Verify
    assert activity is not None
    assert activity["activityId"] == "12345"

    # Verify pagination parameters
    call_args = mock_client.get.call_args
    assert call_args[1]["params"]["page"] == 0
    assert call_args[1]["params"]["count"] == 1


@patch("httpx.Client")
def test_get_latest_activity_empty(mock_client_class, api_client):
    """Test fetching latest activity when none exist."""
    mock_response = MagicMock()
    mock_response.json.return_value = []
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    api_client._client = mock_client

    # Fetch latest
    activity = api_client.get_latest_activity()

    # Verify
    assert activity is None


def test_parse_activity(api_client, sample_activity):
    """Test parsing SmashRun activity data into Activity model."""
    activity_model = api_client.parse_activity(sample_activity)

    assert activity_model.activity_id == "12345"
    assert activity_model.distance == 10.0
    assert activity_model.duration == 3600
    assert activity_model.cadence_average == 170.0


@patch("httpx.Client")
def test_get_user_info(mock_client_class, api_client):
    """Test fetching user profile information."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "userName": "testuser",
        "email": "test@example.com",
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    api_client._client = mock_client

    # Fetch user info
    user_info = api_client.get_user_info()

    # Verify
    assert user_info["userName"] == "testuser"
    mock_client.get.assert_called_once_with("/my/userinfo")


@patch("httpx.Client")
def test_get_all_activities_since_pagination(mock_client_class, api_client, sample_activity):
    """Test fetching all activities with automatic pagination."""
    # Create multiple pages of results
    page1 = [sample_activity] * 10
    page2 = [sample_activity] * 10
    page3 = [sample_activity] * 5  # Last page (partial)

    mock_responses = [
        MagicMock(json=lambda p1=page1: p1),
        MagicMock(json=lambda p2=page2: p2),
        MagicMock(json=lambda p3=page3: p3),
    ]

    for resp in mock_responses:
        resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.side_effect = mock_responses
    api_client._client = mock_client

    # Fetch all activities
    since_date = date(2024, 1, 1)
    all_activities = api_client.get_all_activities_since(since_date, batch_size=10)

    # Verify
    assert len(all_activities) == 25  # 10 + 10 + 5
    assert mock_client.get.call_count == 3  # 3 pages


def test_count_limit(api_client):
    """Test that count parameter is limited to maximum of 100."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = []
    mock_response.raise_for_status = MagicMock()
    mock_client.get.return_value = mock_response
    api_client._client = mock_client

    # Try to request 200 (should be clamped to 100)
    api_client.get_activities(page=0, count=200)

    call_args = mock_client.get.call_args
    assert call_args[1]["params"]["count"] == 100
