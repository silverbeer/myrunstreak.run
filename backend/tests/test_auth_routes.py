"""Tests for /auth/{signup,login,refresh} — the Supabase Auth proxy.

We mock httpx.post so the endpoints can be exercised without a real Supabase.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient


def _client() -> TestClient:
    from backend.app import create_app

    return TestClient(create_app())


def _mock_response(status_code: int, body: Any) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = body
    return response


@pytest.fixture
def client() -> TestClient:
    return _client()


# ---------------------------------------------------------------------------
# /auth/signup
# ---------------------------------------------------------------------------


def test_signup_returns_session_when_email_confirmation_disabled(client: TestClient) -> None:
    supabase_body = {
        "user": {"id": "00000000-0000-0000-0000-000000000001", "email": "new@example.com"},
        "session": {
            "access_token": "atk",
            "refresh_token": "rtk",
            "expires_in": 3600,
        },
    }
    with patch("backend.routes.auth_routes.httpx.post", return_value=_mock_response(200, supabase_body)):
        r = client.post("/auth/signup", json={"email": "new@example.com", "password": "hunter2hunter2"})

    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] == "atk"
    assert body["refresh_token"] == "rtk"
    assert body["user"] == {"id": "00000000-0000-0000-0000-000000000001", "email": "new@example.com"}
    assert "Account created" in body["message"]


def test_signup_returns_no_session_when_confirmation_required(client: TestClient) -> None:
    supabase_body = {
        "user": {"id": "00000000-0000-0000-0000-000000000002", "email": "pending@example.com"},
        "session": None,
    }
    with patch("backend.routes.auth_routes.httpx.post", return_value=_mock_response(200, supabase_body)):
        r = client.post(
            "/auth/signup", json={"email": "pending@example.com", "password": "hunter2hunter2"}
        )

    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] is None
    assert body["refresh_token"] is None
    assert "Check your email" in body["message"]


def test_signup_propagates_supabase_error(client: TestClient) -> None:
    supabase_body = {"msg": "User already registered"}
    with patch(
        "backend.routes.auth_routes.httpx.post",
        return_value=_mock_response(422, supabase_body),
    ):
        r = client.post("/auth/signup", json={"email": "dup@example.com", "password": "hunter2hunter2"})

    assert r.status_code == 422
    assert r.json()["detail"] == "User already registered"


def test_signup_rejects_invalid_email(client: TestClient) -> None:
    r = client.post("/auth/signup", json={"email": "not-an-email", "password": "hunter2hunter2"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# /auth/login
# ---------------------------------------------------------------------------


def test_login_returns_session(client: TestClient) -> None:
    supabase_body = {
        "access_token": "atk",
        "refresh_token": "rtk",
        "expires_in": 3600,
        "user": {"id": "00000000-0000-0000-0000-000000000003", "email": "u@example.com"},
    }
    with patch("backend.routes.auth_routes.httpx.post", return_value=_mock_response(200, supabase_body)):
        r = client.post("/auth/login", json={"email": "u@example.com", "password": "hunter2hunter2"})

    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] == "atk"
    assert body["refresh_token"] == "rtk"
    assert body["user"]["email"] == "u@example.com"


def test_login_propagates_invalid_credentials(client: TestClient) -> None:
    supabase_body = {"error": "invalid_grant", "error_description": "Invalid login credentials"}
    with patch(
        "backend.routes.auth_routes.httpx.post",
        return_value=_mock_response(400, supabase_body),
    ):
        r = client.post("/auth/login", json={"email": "u@example.com", "password": "wrong"})

    assert r.status_code == 400
    assert r.json()["detail"] == "Invalid login credentials"


# ---------------------------------------------------------------------------
# /auth/refresh
# ---------------------------------------------------------------------------


def test_refresh_returns_new_tokens(client: TestClient) -> None:
    supabase_body = {
        "access_token": "atk2",
        "refresh_token": "rtk2",
        "expires_in": 3600,
    }
    with patch("backend.routes.auth_routes.httpx.post", return_value=_mock_response(200, supabase_body)):
        r = client.post("/auth/refresh", json={"refresh_token": "rtk1"})

    assert r.status_code == 200
    assert r.json() == {"access_token": "atk2", "refresh_token": "rtk2", "expires_in": 3600}


def test_refresh_rejects_expired_token(client: TestClient) -> None:
    supabase_body = {"error": "invalid_grant", "error_description": "Refresh token expired"}
    with patch(
        "backend.routes.auth_routes.httpx.post",
        return_value=_mock_response(400, supabase_body),
    ):
        r = client.post("/auth/refresh", json={"refresh_token": "expired"})

    assert r.status_code == 400
    assert r.json()["detail"] == "Refresh token expired"


# ---------------------------------------------------------------------------
# Network/transport failure surfaces 503
# ---------------------------------------------------------------------------


def test_supabase_unreachable_returns_503(client: TestClient) -> None:
    with patch(
        "backend.routes.auth_routes.httpx.post",
        side_effect=httpx.ConnectError("connection refused"),
    ):
        r = client.post("/auth/login", json={"email": "u@example.com", "password": "hunter2hunter2"})

    assert r.status_code == 503
    assert "unavailable" in r.json()["detail"].lower()
