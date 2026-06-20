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
    with patch(
        "backend.routes.auth_routes.httpx.request", return_value=_mock_response(200, supabase_body)
    ):
        r = client.post(
            "/auth/signup", json={"email": "new@example.com", "password": "hunter2hunter2"}
        )

    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] == "atk"
    assert body["refresh_token"] == "rtk"
    assert body["user"] == {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "new@example.com",
    }
    assert "Account created" in body["message"]


def test_signup_returns_no_session_when_confirmation_required(client: TestClient) -> None:
    supabase_body = {
        "user": {"id": "00000000-0000-0000-0000-000000000002", "email": "pending@example.com"},
        "session": None,
    }
    with patch(
        "backend.routes.auth_routes.httpx.request", return_value=_mock_response(200, supabase_body)
    ):
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
        "backend.routes.auth_routes.httpx.request",
        return_value=_mock_response(422, supabase_body),
    ):
        r = client.post(
            "/auth/signup", json={"email": "dup@example.com", "password": "hunter2hunter2"}
        )

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
    with patch(
        "backend.routes.auth_routes.httpx.request", return_value=_mock_response(200, supabase_body)
    ):
        r = client.post(
            "/auth/login", json={"email": "u@example.com", "password": "hunter2hunter2"}
        )

    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] == "atk"
    assert body["refresh_token"] == "rtk"
    assert body["user"]["email"] == "u@example.com"


def test_login_propagates_invalid_credentials(client: TestClient) -> None:
    supabase_body = {"error": "invalid_grant", "error_description": "Invalid login credentials"}
    with patch(
        "backend.routes.auth_routes.httpx.request",
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
    with patch(
        "backend.routes.auth_routes.httpx.request", return_value=_mock_response(200, supabase_body)
    ):
        r = client.post("/auth/refresh", json={"refresh_token": "rtk1"})

    assert r.status_code == 200
    assert r.json() == {"access_token": "atk2", "refresh_token": "rtk2", "expires_in": 3600}


def test_refresh_rejects_expired_token(client: TestClient) -> None:
    supabase_body = {"error": "invalid_grant", "error_description": "Refresh token expired"}
    with patch(
        "backend.routes.auth_routes.httpx.request",
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
        "backend.routes.auth_routes.httpx.request",
        side_effect=httpx.ConnectError("connection refused"),
    ):
        r = client.post(
            "/auth/login", json={"email": "u@example.com", "password": "hunter2hunter2"}
        )

    assert r.status_code == 503
    assert "unavailable" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Password reset (forgot + reset)
# ---------------------------------------------------------------------------


def test_forgot_password_returns_generic_success(client: TestClient) -> None:
    """Supabase /recover returns 200 with empty body on success.

    We always reply with the same message regardless of whether the email
    exists (Supabase's own behavior — don't leak which addresses are
    registered)."""
    with patch(
        "backend.routes.auth_routes.httpx.request",
        return_value=_mock_response(200, ""),
    ) as mock_req:
        r = client.post("/auth/forgot-password", json={"email": "u@example.com"})

    assert r.status_code == 200
    assert "reset link" in r.json()["message"].lower()
    # Verify we forwarded the email + the default redirect_to to Supabase /recover
    args, kwargs = mock_req.call_args
    assert args[0] == "POST"
    assert args[1].endswith("/auth/v1/recover")
    assert kwargs["json"]["email"] == "u@example.com"
    assert kwargs["json"]["redirect_to"] == "https://myrunstreak.run/auth/reset-password"


def test_forgot_password_accepts_explicit_redirect(client: TestClient) -> None:
    """Frontend can override redirect_to (e.g. for local dev or staging)."""
    with patch(
        "backend.routes.auth_routes.httpx.request",
        return_value=_mock_response(200, ""),
    ) as mock_req:
        r = client.post(
            "/auth/forgot-password",
            json={
                "email": "u@example.com",
                "redirect_to": "http://localhost:5174/auth/reset-password",
            },
        )

    assert r.status_code == 200
    _, kwargs = mock_req.call_args
    assert kwargs["json"]["redirect_to"] == "http://localhost:5174/auth/reset-password"


def test_forgot_password_rejects_invalid_email(client: TestClient) -> None:
    r = client.post("/auth/forgot-password", json={"email": "not-an-email"})
    assert r.status_code == 422


def test_reset_password_forwards_to_supabase_user_put(client: TestClient) -> None:
    """Supabase /user PUT returns 200 with a (possibly large) user object.

    We return only a static success message so we don't echo any user
    fields back to the unauthenticated reset page."""
    supabase_body = {"id": "uid-1", "email": "u@example.com"}
    with patch(
        "backend.routes.auth_routes.httpx.request",
        return_value=_mock_response(200, supabase_body),
    ) as mock_req:
        r = client.post(
            "/auth/reset-password",
            json={"access_token": "recovery-tok", "new_password": "newhunter22"},
        )

    assert r.status_code == 200
    assert "updated" in r.json()["message"].lower()

    args, kwargs = mock_req.call_args
    assert args[0] == "PUT"
    assert args[1].endswith("/auth/v1/user")
    assert kwargs["json"] == {"password": "newhunter22"}
    assert kwargs["headers"]["Authorization"] == "Bearer recovery-tok"


def test_reset_password_propagates_invalid_token(client: TestClient) -> None:
    """Expired/invalid recovery token → Supabase returns 401, we forward."""
    with patch(
        "backend.routes.auth_routes.httpx.request",
        return_value=_mock_response(401, {"msg": "Invalid token"}),
    ):
        r = client.post(
            "/auth/reset-password",
            json={"access_token": "bad", "new_password": "newhunter22"},
        )

    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid token"


def test_reset_password_propagates_weak_password(client: TestClient) -> None:
    """Supabase enforces password policy server-side."""
    with patch(
        "backend.routes.auth_routes.httpx.request",
        return_value=_mock_response(
            422,
            {"msg": "Password should be at least 6 characters"},
        ),
    ):
        r = client.post(
            "/auth/reset-password",
            json={"access_token": "tok", "new_password": "x"},
        )

    assert r.status_code == 422
    assert "6 characters" in r.json()["detail"]
