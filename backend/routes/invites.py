"""/invites — admin-issued invite-only onboarding (SB-188).

Issue + list are admin-only (ADMIN_USER_IDS allowlist). Redeem is public (the
token is the credential): it admin-creates the Supabase user, links a users
row, consumes the invite, and returns a session. Open signups must be disabled
in the Supabase dashboard so this is the only way in.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from backend.admin import require_admin
from backend.auth import authenticate_request
from backend.config import get_settings
from backend.routes.auth_routes import _proxy_supabase_auth
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from src.shared.models import Invite, InviteCreate
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import (
    InvitesRepository,
    UserRolesRepository,
    UsersRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invites", tags=["invites"])


class RedeemRequest(BaseModel):
    token: str = Field(min_length=8, description="The invite token")
    password: str = Field(min_length=6, description="Password for the new account")


def _admin_create_user(email: str, password: str) -> dict[str, Any]:
    """Create a confirmed Supabase auth user via the service-role admin API."""
    settings = get_settings()
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    try:
        response = httpx.post(
            url,
            headers=headers,
            json={"email": email, "password": password, "email_confirm": True},
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        logger.exception("Supabase admin create_user failed")
        raise HTTPException(status_code=503, detail="Auth service unavailable") from exc
    if response.status_code >= 400:
        detail = "Could not create account"
        try:
            body = response.json()
            if isinstance(body, dict):
                detail = body.get("msg") or body.get("error_description") or detail
        except ValueError:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)
    return dict(response.json())


@router.post("", response_model=Invite, status_code=status.HTTP_201_CREATED)
def issue_invite(
    body: InviteCreate,
    user_id: UUID = Depends(authenticate_request),
) -> Invite:
    """Issue an invite (admin only). Returns the invite incl. its token."""
    require_admin(user_id)
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=body.expires_in_days)
    row = InvitesRepository(get_supabase_client()).create(
        created_by=user_id,
        email=body.email,
        token=token,
        expires_at=expires_at,
        grant_role=body.grant_role.value if body.grant_role else None,
    )
    return Invite(**row)


@router.get("", response_model=list[Invite])
def list_invites(
    user_id: UUID = Depends(authenticate_request),
) -> list[Invite]:
    """List invites you've issued (admin only)."""
    require_admin(user_id)
    rows = InvitesRepository(get_supabase_client()).list_by_creator(user_id)
    return [Invite(**r) for r in rows]


@router.post("/redeem")
def redeem_invite(body: RedeemRequest) -> dict[str, Any]:
    """Redeem an invite token: create the account + return a session.

    Public (the token is the credential). The account's email is taken from the
    invite, not the request, so a token can only ever create the invited address.
    """
    supabase = get_supabase_client()
    invites = InvitesRepository(supabase)

    invite = invites.get_by_token(body.token)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite token")
    if invite.get("redeemed_at"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invite already redeemed")
    expires_at = datetime.fromisoformat(invite["expires_at"])
    if expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite expired")

    email = invite["email"]
    auth_user = _admin_create_user(email, body.password)
    auth_uid = UUID(str(auth_user["id"]))

    # users.user_id must equal the auth uid (RLS + invites FK invariant).
    UsersRepository(supabase).upsert_user_with_id(auth_uid, email=email)
    # Grant the invite's role (e.g. coach) so they can act immediately (SB-204).
    if invite.get("grant_role"):
        UserRolesRepository(supabase).grant(auth_uid, str(invite["grant_role"]))
    invites.mark_redeemed(body.token, auth_uid, datetime.now(UTC))

    # Hand back a live session so the invitee is logged straight in.
    session = _proxy_supabase_auth(
        "/token?grant_type=password", {"email": email, "password": body.password}
    )
    return {
        "access_token": session["access_token"],
        "refresh_token": session["refresh_token"],
        "expires_in": session.get("expires_in"),
        "user": {"id": str(auth_uid), "email": email},
    }
