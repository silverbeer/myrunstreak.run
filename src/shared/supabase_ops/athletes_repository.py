"""Repositories for the coach platform foundation (SB-195).

The backend connects with the service-role key (bypasses RLS), so every method
scopes by the relevant id in code. Access decisions live in the backend's
can_access_athlete; these repos are the plain data layer.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from supabase import Client


def _name_tokens(name: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9]+", " ", name.lower()).split())


def is_possible_duplicate(
    new_name: str,
    new_birth_year: int | None,
    existing_name: str,
    existing_birth_year: int | None,
) -> bool:
    """Heuristic athlete-duplicate match (SB-349): one name's tokens are a subset
    of the other's AND — when both birth years are known — they match; if either
    year is unknown, require identical token sets. Catches 'Gabe' vs 'Gabe Drake'
    born the same year, without flagging unrelated same-first-name people of
    different ages."""
    nt, et = _name_tokens(new_name), _name_tokens(existing_name)
    if not nt or not et:
        return False
    if not (nt <= et or et <= nt):
        return False
    if new_birth_year is not None and existing_birth_year is not None:
        return new_birth_year == existing_birth_year
    return nt == et


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

    def find_possible_duplicates(
        self, display_name: str, birth_year: int | None
    ) -> list[dict[str, Any]]:
        """Existing athletes that look like the same person (SB-349). Scans the
        athletes table (small) and filters with is_possible_duplicate."""
        rows = cast(
            list[dict[str, Any]],
            self.supabase.table("athletes").select("id,display_name,birth_year").execute().data,
        )
        return [
            r
            for r in rows
            if is_possible_duplicate(
                display_name, birth_year, r["display_name"], r.get("birth_year")
            )
        ]

    def get_by_linked_user(self, user_id: UUID) -> dict[str, Any] | None:
        """The athlete this user IS (via linked_user_id), or None."""
        result = (
            self.supabase.table("athletes")
            .select("*")
            .eq("linked_user_id", str(user_id))
            .limit(1)
            .execute()
        )
        data = cast(list[dict[str, Any]], result.data)
        return data[0] if data else None

    def get_profile(self, athlete_id: UUID) -> dict[str, Any] | None:
        """The 1:1 athlete_profiles row, or None if not created yet."""
        result = (
            self.supabase.table("athlete_profiles")
            .select("*")
            .eq("athlete_id", str(athlete_id))
            .execute()
        )
        data = cast(list[dict[str, Any]], result.data)
        return data[0] if data else None

    def upsert_profile(
        self, athlete_id: UUID, fields: dict[str, Any], updated_by: UUID
    ) -> dict[str, Any]:
        """Create/patch the profile with the given fields (already permission-
        filtered by the caller). Keeps athletes.birth_year in sync with DOB."""
        row = {
            "athlete_id": str(athlete_id),
            "updated_by": str(updated_by),
            "updated_at": datetime.now(UTC).isoformat(),
            **fields,
        }
        result = (
            self.supabase.table("athlete_profiles").upsert(row, on_conflict="athlete_id").execute()
        )
        # Derive birth_year from DOB so the lean athletes row stays consistent.
        dob = fields.get("date_of_birth")
        if dob:
            year = int(str(dob)[:4])
            self.supabase.table("athletes").update({"birth_year": year}).eq(
                "id", str(athlete_id)
            ).execute()
        return cast(list[dict[str, Any]], result.data)[0]

    def update_core(self, athlete_id: UUID, fields: dict[str, Any]) -> None:
        """Update core columns on the athletes row (display_name, birth_year)."""
        self.supabase.table("athletes").update(fields).eq("id", str(athlete_id)).execute()

    def link_user(self, athlete_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Link a logged-in user to this athlete (athletes.linked_user_id).

        Onboards the athlete as user #2 (SB-212 P4-2): once set, the linked user
        reaches their own athlete-scoped rows via the linked_user_id RLS.
        """
        result = (
            self.supabase.table("athletes")
            .update({"linked_user_id": str(user_id)})
            .eq("id", str(athlete_id))
            .execute()
        )
        return cast(list[dict[str, Any]], result.data)[0]

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
        """Start an active coaching link, returning the existing one if already active.

        Idempotent: a coach already active on the athlete is a no-op that returns
        the current link rather than a duplicate INSERT, which would violate the
        ``idx_coach_athletes_active`` partial unique index and surface as a 500.
        """
        existing = (
            self.supabase.table("coach_athletes")
            .select("*")
            .eq("coach_id", str(coach_id))
            .eq("athlete_id", str(athlete_id))
            .eq("status", "active")
            .execute()
        )
        rows = cast(list[dict[str, Any]], existing.data)
        if rows:
            return rows[0]
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
