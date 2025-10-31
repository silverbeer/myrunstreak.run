"""Tests for SmashRun OAuth client."""

from unittest.mock import MagicMock, patch

import pytest

from src.shared.smashrun import SmashRunOAuthClient


@pytest.fixture
def oauth_client():
    """Create OAuth client for testing."""
    return SmashRunOAuthClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost:8000/callback",
    )


def test_oauth_client_initialization(oauth_client):
    """Test OAuth client initialization."""
    assert oauth_client.client_id == "test_client_id"
    assert oauth_client.client_secret == "test_client_secret"
    assert oauth_client.redirect_uri == "http://localhost:8000/callback"
    assert oauth_client.scope == SmashRunOAuthClient.SCOPE_READ_ACTIVITY


def test_get_authorization_url_without_state(oauth_client):
    """Test generating authorization URL without state parameter."""
    url = oauth_client.get_authorization_url()

    assert url.startswith(SmashRunOAuthClient.AUTHORIZATION_ENDPOINT)
    assert "client_id=test_client_id" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fcallback" in url
    assert "response_type=code" in url
    assert "scope=read_activity" in url
    assert "state=" not in url


def test_get_authorization_url_with_state(oauth_client):
    """Test generating authorization URL with state parameter."""
    url = oauth_client.get_authorization_url(state="random_state_123")

    assert url.startswith(SmashRunOAuthClient.AUTHORIZATION_ENDPOINT)
    assert "state=random_state_123" in url


@patch("httpx.Client")
def test_exchange_code_for_token_success(mock_client_class, oauth_client):
    """Test successful token exchange."""
    # Mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_in": 7257600,  # 12 weeks in seconds
        "token_type": "Bearer",
    }
    mock_response.raise_for_status = MagicMock()

    # Mock client
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client_class.return_value = mock_client

    # Exchange code
    token_data = oauth_client.exchange_code_for_token("auth_code_123")

    # Verify
    assert token_data["access_token"] == "test_access_token"
    assert token_data["refresh_token"] == "test_refresh_token"
    assert token_data["token_type"] == "Bearer"

    # Verify POST was called correctly
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == SmashRunOAuthClient.TOKEN_ENDPOINT
    assert call_args[1]["data"]["grant_type"] == "authorization_code"
    assert call_args[1]["data"]["code"] == "auth_code_123"


@patch("httpx.Client")
def test_refresh_access_token_success(mock_client_class, oauth_client):
    """Test successful token refresh."""
    # Mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_in": 7257600,
        "token_type": "Bearer",
    }
    mock_response.raise_for_status = MagicMock()

    # Mock client
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client_class.return_value = mock_client

    # Refresh token
    token_data = oauth_client.refresh_access_token("old_refresh_token")

    # Verify
    assert token_data["access_token"] == "new_access_token"
    assert token_data["token_type"] == "Bearer"

    # Verify POST was called correctly
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[1]["data"]["grant_type"] == "refresh_token"
    assert call_args[1]["data"]["refresh_token"] == "old_refresh_token"


def test_create_authorized_client(oauth_client):
    """Test creating authorized HTTP client."""
    client = oauth_client.create_authorized_client("test_access_token")

    assert client is not None
    assert client.token["access_token"] == "test_access_token"
    assert client.token["token_type"] == "Bearer"


def test_oauth_client_with_write_scope():
    """Test OAuth client with write_activity scope."""
    client = SmashRunOAuthClient(
        client_id="test_id",
        client_secret="test_secret",
        redirect_uri="http://localhost:8000/callback",
        scope=SmashRunOAuthClient.SCOPE_WRITE_ACTIVITY,
    )

    url = client.get_authorization_url()
    assert "scope=write_activity" in url
