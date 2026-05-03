"""Tests for the JWT verification middleware."""

from __future__ import annotations

import time
from unittest.mock import MagicMock
from uuid import UUID

import jwt
import pytest
from fastapi import HTTPException, Request

from backend.auth import authenticate_request

JWT_SECRET = "test-jwt-secret-needs-to-be-long-enough-for-hs256"
USER_UUID = "16eb502d-7fc0-4fce-9107-9931df747e28"


def _request(headers: dict[str, str] | None = None) -> Request:
    """Build a minimal Request stub."""
    request = MagicMock(spec=Request)
    request.headers = headers or {}
    request.state = MagicMock()
    return request


def _hs256(claims: dict[str, object], secret: str = JWT_SECRET) -> str:
    return jwt.encode(claims, secret, algorithm="HS256")


def _valid_token() -> str:
    return _hs256(
        {
            "sub": USER_UUID,
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
    )


class TestAuthenticateRequest:
    def test_accepts_valid_token_and_sets_user_id(self) -> None:
        req = _request({"authorization": f"Bearer {_valid_token()}"})
        user_id = authenticate_request(req)
        assert user_id == UUID(USER_UUID)
        assert req.state.user_id == UUID(USER_UUID)

    def test_accepts_lowercase_bearer(self) -> None:
        req = _request({"authorization": f"bearer {_valid_token()}"})
        assert authenticate_request(req) == UUID(USER_UUID)

    def test_missing_header_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc:
            authenticate_request(_request({}))
        assert exc.value.status_code == 401
        assert "Missing or malformed" in exc.value.detail

    def test_non_bearer_header_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc:
            authenticate_request(_request({"authorization": "Basic xyz"}))
        assert exc.value.status_code == 401

    def test_empty_token_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc:
            authenticate_request(_request({"authorization": "Bearer "}))
        assert exc.value.status_code == 401

    def test_wrong_secret_raises_401(self) -> None:
        bad = _hs256(
            {
                "sub": USER_UUID,
                "aud": "authenticated",
                "exp": int(time.time()) + 3600,
            },
            secret="wrong-secret",
        )
        with pytest.raises(HTTPException) as exc:
            authenticate_request(_request({"authorization": f"Bearer {bad}"}))
        assert exc.value.status_code == 401

    def test_expired_token_raises_401(self) -> None:
        expired = _hs256(
            {
                "sub": USER_UUID,
                "aud": "authenticated",
                "exp": int(time.time()) - 3600,
            }
        )
        with pytest.raises(HTTPException) as exc:
            authenticate_request(_request({"authorization": f"Bearer {expired}"}))
        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail.lower()

    def test_wrong_audience_raises_401(self) -> None:
        bad_aud = _hs256(
            {
                "sub": USER_UUID,
                "aud": "anonymous",
                "exp": int(time.time()) + 3600,
            }
        )
        with pytest.raises(HTTPException) as exc:
            authenticate_request(_request({"authorization": f"Bearer {bad_aud}"}))
        assert exc.value.status_code == 401

    def test_missing_sub_claim_raises_401(self) -> None:
        no_sub = _hs256(
            {"aud": "authenticated", "exp": int(time.time()) + 3600},
        )
        with pytest.raises(HTTPException) as exc:
            authenticate_request(_request({"authorization": f"Bearer {no_sub}"}))
        assert exc.value.status_code == 401

    def test_non_uuid_sub_raises_401(self) -> None:
        bad_sub = _hs256(
            {
                "sub": "not-a-uuid",
                "aud": "authenticated",
                "exp": int(time.time()) + 3600,
            }
        )
        with pytest.raises(HTTPException) as exc:
            authenticate_request(_request({"authorization": f"Bearer {bad_sub}"}))
        assert exc.value.status_code == 401
