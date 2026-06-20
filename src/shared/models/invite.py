"""Models for invite-only onboarding (SB-188)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class InviteCreate(BaseModel):
    """Admin request to issue an invite."""

    email: str = Field(min_length=3, description="Who the invite is for")
    expires_in_days: int = Field(
        default=14, ge=1, le=90, description="Days until the token expires"
    )


class Invite(BaseModel):
    """An issued invite (the token is only meaningful before redemption)."""

    id: UUID
    token: str
    email: str
    created_by: UUID
    expires_at: datetime
    redeemed_at: datetime | None = None
    redeemed_by: UUID | None = None
    created_at: datetime
