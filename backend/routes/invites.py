"""/invites — admin-issued invite-only onboarding (SB-188).

Issue + list are admin-only (ADMIN_USER_IDS allowlist). Redemption happens at
signup (a later slice) and is server-side, so it isn't exposed here.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from backend.admin import require_admin
from backend.auth import authenticate_request
from fastapi import APIRouter, Depends, status
from src.shared.models import Invite, InviteCreate
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import InvitesRepository

router = APIRouter(prefix="/invites", tags=["invites"])


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
        created_by=user_id, email=body.email, token=token, expires_at=expires_at
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
