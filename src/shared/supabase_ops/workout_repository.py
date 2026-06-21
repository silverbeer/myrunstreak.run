"""Repositories for the Athlete Training Tracker tables (SB-191).

exercises (catalog) + workout_templates/template_items + workout_sessions/
exercise_sets. Like the other repos, the backend uses the service-role key, so
every query scopes by ``user_id`` itself; the DB policies are a second guard.

Templates and sessions are created with their children inline (items / sets) in
one call, and read back with the children nested.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any, cast
from uuid import UUID

from supabase import Client


def _owner_fields(user_id: UUID, athlete_id: UUID | None) -> dict[str, str]:
    """Owner columns for a row. Self → user_id only. Athlete (act-as) → also
    athlete_id (the subject) + created_by (the acting coach, for audit)."""
    fields = {"user_id": str(user_id)}
    if athlete_id is not None:
        fields["athlete_id"] = str(athlete_id)
        fields["created_by"] = str(user_id)
    return fields


def _scope(query: Any, user_id: UUID, athlete_id: UUID | None) -> Any:
    """Limit a query to the owner. Athlete rows by athlete_id; self rows by
    user_id AND athlete_id IS NULL (so a coach's own rows never leak athletes')."""
    if athlete_id is not None:
        return query.eq("athlete_id", str(athlete_id))
    return query.eq("user_id", str(user_id)).is_("athlete_id", "null")


class ExercisesRepository:
    """Read-only global movement catalog."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def list_all(self) -> list[dict[str, Any]]:
        result = (
            self.supabase.table("exercises").select("*").order("category").order("key").execute()
        )
        return cast(list[dict[str, Any]], result.data)

    def keys(self) -> set[str]:
        result = self.supabase.table("exercises").select("key").execute()
        return {r["key"] for r in cast(list[dict[str, Any]], result.data)}


class WorkoutTemplatesRepository:
    """Per-user workout templates (the coach's plan) + their items."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def create(
        self, user_id: UUID, payload: dict[str, Any], athlete_id: UUID | None = None
    ) -> dict[str, Any]:
        items: Sequence[dict[str, Any]] = payload.pop("items", []) or []
        owner = _owner_fields(user_id, athlete_id)
        row = self.supabase.table("workout_templates").insert({**payload, **owner}).execute()
        template = cast(list[dict[str, Any]], row.data)[0]
        if items:
            item_rows = [{**it, **owner, "template_id": template["id"]} for it in items]
            self.supabase.table("template_items").insert(item_rows).execute()
        got = self.get(user_id, UUID(template["id"]), athlete_id)
        assert got is not None
        return got

    def list(self, user_id: UUID, athlete_id: UUID | None = None) -> list[dict[str, Any]]:
        query = _scope(self.supabase.table("workout_templates").select("*"), user_id, athlete_id)
        result = query.order("created_at", desc=True).execute()
        return cast(list[dict[str, Any]], result.data)

    def get(
        self, user_id: UUID, template_id: UUID, athlete_id: UUID | None = None
    ) -> dict[str, Any] | None:
        query = _scope(
            self.supabase.table("workout_templates").select("*").eq("id", str(template_id)),
            user_id,
            athlete_id,
        )
        rows = cast(list[dict[str, Any]], query.execute().data)
        if not rows:
            return None
        template = rows[0]
        items = (
            self.supabase.table("template_items")
            .select("*")
            .eq("template_id", str(template_id))
            .order("position")
            .execute()
        )
        template["items"] = cast(list[dict[str, Any]], items.data)
        return template

    def delete(self, user_id: UUID, template_id: UUID, athlete_id: UUID | None = None) -> bool:
        query = _scope(
            self.supabase.table("workout_templates").delete().eq("id", str(template_id)),
            user_id,
            athlete_id,
        )
        return bool(cast(list[dict[str, Any]], query.execute().data))


class WorkoutSessionsRepository:
    """Per-user logged sessions + their exercise sets."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def create(
        self, user_id: UUID, payload: dict[str, Any], athlete_id: UUID | None = None
    ) -> dict[str, Any]:
        sets: Sequence[dict[str, Any]] = payload.pop("sets", []) or []
        owner = _owner_fields(user_id, athlete_id)
        row = self.supabase.table("workout_sessions").insert({**payload, **owner}).execute()
        session = cast(list[dict[str, Any]], row.data)[0]
        if sets:
            set_rows = [{**s, **owner, "session_id": session["id"]} for s in sets]
            self.supabase.table("exercise_sets").insert(set_rows).execute()
        got = self.get(user_id, UUID(session["id"]), athlete_id)
        assert got is not None
        return got

    def list(
        self,
        user_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 100,
        athlete_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        query = _scope(self.supabase.table("workout_sessions").select("*"), user_id, athlete_id)
        if date_from is not None:
            query = query.gte("session_date", date_from.isoformat())
        if date_to is not None:
            query = query.lte("session_date", date_to.isoformat())
        result = query.order("session_date", desc=True).limit(limit).execute()
        return cast(list[dict[str, Any]], result.data)

    def get(
        self, user_id: UUID, session_id: UUID, athlete_id: UUID | None = None
    ) -> dict[str, Any] | None:
        query = _scope(
            self.supabase.table("workout_sessions").select("*").eq("id", str(session_id)),
            user_id,
            athlete_id,
        )
        rows = cast(list[dict[str, Any]], query.execute().data)
        if not rows:
            return None
        session = rows[0]
        sets = (
            self.supabase.table("exercise_sets")
            .select("*")
            .eq("session_id", str(session_id))
            .order("round_number")
            .order("set_index")
            .execute()
        )
        session["sets"] = cast(list[dict[str, Any]], sets.data)
        return session

    def delete(self, user_id: UUID, session_id: UUID, athlete_id: UUID | None = None) -> bool:
        query = _scope(
            self.supabase.table("workout_sessions").delete().eq("id", str(session_id)),
            user_id,
            athlete_id,
        )
        return bool(cast(list[dict[str, Any]], query.execute().data))
