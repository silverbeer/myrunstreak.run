"""/auth/* — Supabase Auth proxy + SmashRun OAuth linking.

The signup/login/refresh endpoints proxy to Supabase Auth so that clients
(stk CLI, web frontend) only need to know about api.myrunstreak.run.
Supabase URL/keys never leave the backend.

The link/login-url + link/callback endpoints handle SmashRun OAuth account
linking after a user is authenticated.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx
from backend.auth import authenticate_request
from backend.config import get_settings
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from src.shared.secrets import get_smashrun_oauth_credentials
from src.shared.smashrun import SmashRunAPIClient, SmashRunOAuthClient
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import TokenRepository, UsersRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_SUPABASE_TIMEOUT = 10.0


class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


def _supabase_auth_url(path: str) -> str:
    settings = get_settings()
    return f"{settings.supabase_url.rstrip('/')}/auth/v1{path}"


def _supabase_headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "apikey": settings.supabase_anon_key,
        "Content-Type": "application/json",
    }


def _proxy_supabase_auth(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST to Supabase Auth and surface its error JSON on failure.

    Supabase returns ``{"msg": "..."}`` on most auth errors; we forward both
    the status code and a sanitized message so the CLI/frontend can show
    something useful without leaking implementation details.
    """
    try:
        response = httpx.post(
            _supabase_auth_url(path),
            headers=_supabase_headers(),
            json=payload,
            timeout=_SUPABASE_TIMEOUT,
        )
    except httpx.RequestError as exc:
        logger.exception("Supabase auth request failed")
        raise HTTPException(status_code=503, detail="Auth service unavailable") from exc

    if response.status_code >= 400:
        detail = "Authentication failed"
        try:
            body = response.json()
            if isinstance(body, dict):
                detail = body.get("msg") or body.get("error_description") or body.get("error") or detail
        except ValueError:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)

    result: dict[str, Any] = response.json()
    return result


@router.post("/signup")
async def signup(body: SignupRequest) -> dict[str, Any]:
    """Create a new myrunstreak account.

    Returns a session immediately when email-confirmation is disabled.
    When enabled, returns ``session=None`` and a message instructing the
    user to confirm via email before logging in.
    """
    data = _proxy_supabase_auth("/signup", {"email": body.email, "password": body.password})
    user = data.get("user") or {}
    session = data.get("session")
    if session:
        return {
            "user": {"id": user.get("id"), "email": user.get("email")},
            "access_token": session["access_token"],
            "refresh_token": session["refresh_token"],
            "expires_in": session.get("expires_in"),
            "message": "Account created.",
        }
    return {
        "user": {"id": user.get("id"), "email": user.get("email")},
        "access_token": None,
        "refresh_token": None,
        "expires_in": None,
        "message": "Account created. Check your email to confirm before logging in.",
    }


@router.post("/login")
async def login(body: LoginRequest) -> dict[str, Any]:
    """Exchange email + password for an access/refresh token pair."""
    data = _proxy_supabase_auth(
        "/token?grant_type=password",
        {"email": body.email, "password": body.password},
    )
    user = data.get("user") or {}
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data.get("expires_in"),
        "user": {"id": user.get("id"), "email": user.get("email")},
    }


@router.post("/refresh")
async def refresh(body: RefreshRequest) -> dict[str, Any]:
    """Exchange a refresh token for a fresh access/refresh pair."""
    data = _proxy_supabase_auth(
        "/token?grant_type=refresh_token",
        {"refresh_token": body.refresh_token},
    )
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data.get("expires_in"),
    }


@router.get("/login-url")
async def get_login_url(
    redirect_uri: str = Query("http://localhost:9876/callback"),
) -> dict[str, str]:
    creds = get_smashrun_oauth_credentials()
    oauth = SmashRunOAuthClient(
        client_id=creds.get("client_id", ""),
        client_secret=creds.get("client_secret", ""),
        redirect_uri=redirect_uri,
    )
    return {
        "auth_url": oauth.get_authorization_url(state="stk_cli"),
        "redirect_uri": redirect_uri,
    }


@router.post("/callback")
async def handle_auth_callback(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    code = body.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="code is required")
    redirect_uri = body.get("redirect_uri", "http://localhost:9876/callback")

    creds = get_smashrun_oauth_credentials()
    oauth = SmashRunOAuthClient(
        client_id=creds.get("client_id", ""),
        client_secret=creds.get("client_secret", ""),
        redirect_uri=redirect_uri,
    )
    token_data = oauth.exchange_code_for_token(code)
    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]
    expires_in = token_data.get("expires_in")

    with SmashRunAPIClient(access_token=access_token) as api:
        info = api.get_user_info()
        username = info.get("userName", "unknown")
        smashrun_user_id = str(info.get("id", ""))

    supabase = get_supabase_client()
    users_repo = UsersRepository(supabase)
    token_repo = TokenRepository(supabase)

    user, created = users_repo.get_or_create_user_with_source(
        source_type="smashrun",
        source_username=username,
        source_user_id=smashrun_user_id,
        display_name=username,
    )
    user_id = UUID(user["user_id"])

    token_repo.save_user_tokens(
        user_id=user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        source_type="smashrun",
    )

    return {"user_id": str(user_id), "username": username, "created": created}


@router.post("/store-tokens")
async def store_tokens(
    user_id: UUID = Depends(authenticate_request),
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    access_token = body.get("access_token")
    refresh_token = body.get("refresh_token")
    if not access_token or not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="access_token and refresh_token are required",
        )

    supabase = get_supabase_client()
    TokenRepository(supabase).save_user_tokens(
        user_id=user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=body.get("expires_in"),
        source_type="smashrun",
    )
    return {"message": "Tokens stored successfully", "user_id": str(user_id)}
