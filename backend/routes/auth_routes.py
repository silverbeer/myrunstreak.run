"""/auth/* — SmashRun OAuth flow + token storage.

Only /auth/store-tokens requires Supabase auth; the others are public so an
unauthenticated user can begin the OAuth handshake.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from backend.auth import authenticate_request
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from src.shared.secrets import get_smashrun_oauth_credentials
from src.shared.smashrun import SmashRunAPIClient, SmashRunOAuthClient
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import TokenRepository, UsersRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


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
