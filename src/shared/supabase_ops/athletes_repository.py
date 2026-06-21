"""Repositories for the coach platform foundation (SB-195).

The backend connects with the service-role key (bypasses RLS), so every method
scopes by the relevant id in code. Access decisions live in the backend's
can_access_athlete; these repos are the plain data layer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from supabase import Client


class UserRolesRepository:
    """Who is an admin / coach."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def list_roles(self, user_id: UUID) -> set[str]:
        result = (
            self.supabase.table("user_roles").select("role").eq("user_id", str(user_id)).execute()
        )
        return {r["role"] for r in cast(list[dict[str, Any]], result.data)}

    def has_role(self, user_id: UUID, role: str) -> bool:
        return role in self.list_roles(user_id)

    def grant(self, user_id: UUID, role: str) -> None:
        self.supabase.table("user_roles").upsert(
            {"user_id": str(user_id), "role": role}, on_conflict="user_id,role"
        ).execute()


class AthletesRepository:
    """Managed/linked athlete profiles."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def create(
        self,
        created_by: UUID,
        display_name: str,
        birth_year: int | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        row = {"created_by": str(created_by), "display_name": display_name}
        if birth_year is not None:
            row["birth_year"] = birth_year  # type: ignore[assignment]
        if notes is not None:
            row["notes"] = notes
        result = self.supabase.table("athletes").insert(row).execute()
        return cast(list[dict[str, Any]], result.data)[0]

    def get(self, athlete_id: UUID) -> dict[str, Any] | None:
        result = self.supabase.table("athletes").select("*").eq("id", str(athlete_id)).execute()
        data = cast(list[dict[str, Any]], result.data)
        return data[0] if data else None

    def list_for_coach(self, coach_id: UUID) -> list[dict[str, Any]]:
        """Athletes the coach actively coaches (joined via coach_athletes)."""
        links = (
            self.supabase.table("coach_athletes")
            .select("athlete_id")
            .eq("coach_id", str(coach_id))
            .eq("status", "active")
            .execute()
        )
        ids = [r["athlete_id"] for r in cast(list[dict[str, Any]], links.data)]
        if not ids:
            return []
        result = (
            self.supabase.table("athletes")
            .select("*")
            .in_("id", ids)
            .order("display_name")
            .execute()
        )
        return cast(list[dict[str, Any]], result.data)


class CoachAthletesRepository:
    """The coach<->athlete relationship over time."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def active_link_exists(self, coach_id: UUID, athlete_id: UUID) -> bool:
        result = (
            self.supabase.table("coach_athletes")
            .select("id")
            .eq("coach_id", str(coach_id))
            .eq("athlete_id", str(athlete_id))
            .eq("status", "active")
            .execute()
        )
        return bool(cast(list[dict[str, Any]], result.data))

    def assign(self, coach_id: UUID, athlete_id: UUID) -> dict[str, Any]:
        """Start an active coaching link (idempotent on the active uniqueness)."""
        result = (
            self.supabase.table("coach_athletes")
            .insert({"coach_id": str(coach_id), "athlete_id": str(athlete_id)})
            .execute()
        )
        return cast(list[dict[str, Any]], result.data)[0]

    def end(self, coach_id: UUID, athlete_id: UUID) -> int:
        """End the active link; returns rows affected."""
        result = (
            self.supabase.table("coach_athletes")
            .update({"status": "ended", "ended_at": datetime.now(UTC).isoformat()})
            .eq("coach_id", str(coach_id))
            .eq("athlete_id", str(athlete_id))
            .eq("status", "active")
            .execute()
        )
        return len(cast(list[dict[str, Any]], result.data))

    def list_active_for_coach(self, coach_id: UUID) -> list[dict[str, Any]]:
        result = (
            self.supabase.table("coach_athletes")
            .select("*")
            .eq("coach_id", str(coach_id))
            .eq("status", "active")
            .execute()
        )
        return cast(list[dict[str, Any]], result.data)

    def list_active_for_athlete(self, athlete_id: UUID) -> list[dict[str, Any]]:
        """Active coach links for an athlete (caller resolves coach emails)."""
        result = (
            self.supabase.table("coach_athletes")
            .select("*")
            .eq("athlete_id", str(athlete_id))
            .eq("status", "active")
            .execute()
        )
        return cast(list[dict[str, Any]], result.data)
