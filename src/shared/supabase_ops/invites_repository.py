"""Repository for invite-only onboarding (SB-188).

The backend connects with the service-role key (bypasses RLS), so every query
here scopes by the relevant id in code. Issue + redeem are server-side.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from supabase import Client


class InvitesRepository:
    """Issue/list/redeem invites."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def create(
        self,
        created_by: UUID,
        email: str,
        token: str,
        expires_at: datetime,
        grant_role: str | None = None,
        athlete_id: UUID | None = None,
    ) -> dict[str, Any]:
        row = {
            "created_by": str(created_by),
            "email": email,
            "token": token,
            "expires_at": expires_at.isoformat(),
        }
        if grant_role is not None:
            row["grant_role"] = grant_role
        if athlete_id is not None:
            row["athlete_id"] = str(athlete_id)
        result = self.supabase.table("invites").insert(row).execute()
        return cast(list[dict[str, Any]], result.data)[0]

    def list_by_creator(self, created_by: UUID) -> list[dict[str, Any]]:
        result = (
            self.supabase.table("invites")
            .select("*")
            .eq("created_by", str(created_by))
            .order("created_at", desc=True)
            .execute()
        )
        return cast(list[dict[str, Any]], result.data)

    def get_by_token(self, token: str) -> dict[str, Any] | None:
        """Look up an invite by its token (for server-side redemption)."""
        result = self.supabase.table("invites").select("*").eq("token", token).execute()
        data = cast(list[dict[str, Any]], result.data)
        return data[0] if data else None

    def mark_redeemed(self, token: str, redeemed_by: UUID, redeemed_at: datetime) -> dict[str, Any]:
        """Consume an invite. Caller must verify it's unredeemed + unexpired first."""
        result = (
            self.supabase.table("invites")
            .update({"redeemed_at": redeemed_at.isoformat(), "redeemed_by": str(redeemed_by)})
            .eq("token", token)
            .execute()
        )
        return cast(list[dict[str, Any]], result.data)[0]
