"""Repositories for the Athlete Training Tracker tables (SB-191).

exercises (catalog) + workout_templates/template_items + workout_sessions/
exercise_sets. Like the other repos, the backend uses the service-role key, so
every query scopes by ``user_id`` itself; the DB policies are a second guard.

Templates and sessions are created with their children inline (items / sets) in
one call, and read back with the children nested.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from typing import Any, cast
from uuid import UUID

from supabase import Client


def slugify(name: str) -> str:
    """Lowercase, non-alnum → underscore. Base for a generated exercise key."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "exercise"


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
    """Exercise catalog: the canonical public library + coach-owned exercises.

    The backend uses the service-role key (RLS-exempt), so visibility and
    ownership are enforced here in-query: reads = public OR owned by the caller;
    writes are constrained to the caller's own rows.
    """

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def list_all(self) -> list[dict[str, Any]]:
        """Every row, unfiltered (canonical seed maintenance / migrations)."""
        result = (
            self.supabase.table("exercises").select("*").order("category").order("key").execute()
        )
        return cast(list[dict[str, Any]], result.data)

    def list_visible(self, user_id: UUID) -> list[dict[str, Any]]:
        """Exercises the user can use: the public library + their own private ones."""
        result = (
            self.supabase.table("exercises")
            .select("*")
            .or_(f"visibility.eq.public,owner_id.eq.{user_id}")
            .order("display_name")
            .execute()
        )
        return cast(list[dict[str, Any]], result.data)

    def search(self, user_id: UUID, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Fuzzy match over display_name + aliases across the visible catalog.

        Drives search-first selection and the publish-time dedup warning. The
        catalog is small, so we match in Python (case-insensitive substring)
        rather than a DB text index; move to trigram/tsvector if it grows.
        """
        q = query.strip().lower()
        if not q:
            return []
        hits = []
        for row in self.list_visible(user_id):
            haystay = [row.get("display_name", "")] + list(row.get("aliases") or [])
            if any(q in str(h).lower() for h in haystay):
                hits.append(row)
            if len(hits) >= limit:
                break
        return hits

    def get(self, key: str) -> dict[str, Any] | None:
        result = self.supabase.table("exercises").select("*").eq("key", key).execute()
        rows = cast(list[dict[str, Any]], result.data)
        return rows[0] if rows else None

    def keys(self) -> set[str]:
        result = self.supabase.table("exercises").select("key").execute()
        return {r["key"] for r in cast(list[dict[str, Any]], result.data)}

    def _unique_key(self, display_name: str) -> str:
        """Generate a globally-unique slug key from a name (dedupe with -2, -3…)."""
        base = slugify(display_name)
        taken = self.keys()
        if base not in taken:
            return base
        i = 2
        while f"{base}_{i}" in taken:
            i += 1
        return f"{base}_{i}"

    def create(self, user_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a coach-owned exercise; the key is generated to stay unique."""
        row = {
            **payload,
            "key": self._unique_key(payload["display_name"]),
            "owner_id": str(user_id),
            "created_by": str(user_id),
        }
        result = self.supabase.table("exercises").insert(row).execute()
        return cast(list[dict[str, Any]], result.data)[0]

    def update(
        self, user_id: UUID, key: str, patch: dict[str, Any], *, is_admin: bool = False
    ) -> dict[str, Any] | None:
        """Patch an exercise. A coach may patch only their own; an admin may
        patch any (including the canonical library). None if not found / not
        theirs."""
        query = self.supabase.table("exercises").update(patch).eq("key", key)
        if not is_admin:
            query = query.eq("owner_id", str(user_id))
        result = query.execute()
        rows = cast(list[dict[str, Any]], result.data)
        return rows[0] if rows else None

    def publish(self, user_id: UUID, key: str) -> dict[str, Any] | None:
        """Promote an owned private exercise to the public library."""
        return self.update(user_id, key, {"visibility": "public"})

    def delete(self, user_id: UUID, key: str) -> bool:
        """Delete an exercise the caller owns. False if not found / not theirs."""
        result = (
            self.supabase.table("exercises")
            .delete()
            .eq("key", key)
            .eq("owner_id", str(user_id))
            .execute()
        )
        return bool(cast(list[dict[str, Any]], result.data))


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

    def update(
        self,
        user_id: UUID,
        template_id: UUID,
        payload: dict[str, Any],
        athlete_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        """Update a template the caller owns and replace its items. None if not
        found / not theirs."""
        if self.get(user_id, template_id, athlete_id) is None:
            return None

        items: Sequence[dict[str, Any]] | None = payload.pop("items", None)
        if payload:
            self.supabase.table("workout_templates").update(payload).eq(
                "id", str(template_id)
            ).execute()

        if items is not None:
            # Replace the item set wholesale (simplest correct edit).
            self.supabase.table("template_items").delete().eq(
                "template_id", str(template_id)
            ).execute()
            if items:
                owner = _owner_fields(user_id, athlete_id)
                item_rows = [{**it, **owner, "template_id": str(template_id)} for it in items]
                self.supabase.table("template_items").insert(item_rows).execute()

        return self.get(user_id, template_id, athlete_id)

    def list(self, user_id: UUID, athlete_id: UUID | None = None) -> list[dict[str, Any]]:
        query = _scope(self.supabase.table("workout_templates").select("*"), user_id, athlete_id)
        templates = cast(list[dict[str, Any]], query.order("created_at", desc=True).execute().data)
        if not templates:
            return templates

        # Attach items in one batched query (so callers can render the full plan
        # without an extra GET per template).
        ids = [t["id"] for t in templates]
        items = (
            self.supabase.table("template_items")
            .select("*")
            .in_("template_id", ids)
            .order("position")
            .execute()
        )
        by_template: dict[str, list[dict[str, Any]]] = {}
        for it in cast(list[dict[str, Any]], items.data):
            by_template.setdefault(it["template_id"], []).append(it)
        for t in templates:
            t["items"] = by_template.get(t["id"], [])
        return templates

    def list_for_athletes(self, athlete_ids: Sequence[UUID]) -> list[dict[str, Any]]:
        """Template header rows (no items) across a coach's athletes, newest
        first. Feeds the coach home aggregate (SB-266); callers hold the
        athlete set, so access is enforced upstream."""
        if not athlete_ids:
            return []
        result = (
            self.supabase.table("workout_templates")
            .select("*")
            .in_("athlete_id", [str(a) for a in athlete_ids])
            .order("created_at", desc=True)
            .execute()
        )
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

    def list_for_athletes(
        self, athlete_ids: Sequence[UUID], limit: int = 10
    ) -> list[dict[str, Any]]:
        """Recent sessions across a coach's athletes, newest first (no sets).
        Feeds the coach home aggregate (SB-266); access enforced upstream."""
        if not athlete_ids:
            return []
        result = (
            self.supabase.table("workout_sessions")
            .select("*")
            .in_("athlete_id", [str(a) for a in athlete_ids])
            .order("session_date", desc=True)
            .limit(limit)
            .execute()
        )
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
