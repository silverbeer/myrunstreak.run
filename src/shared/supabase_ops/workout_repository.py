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

from src.shared.exercise_matching import find_duplicate_candidates, matches_query
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
        catalog is small, so we match in Python (normalized substring) rather
        than a DB text index; move to trigram/tsvector if it grows.

        Both sides are normalized (SB-454) so punctuation and plurals don't hide
        a row from the coach looking for it — "push ups" has to find "Push-ups",
        because a search that returns nothing is how duplicates get created.
        """
        if not query.strip():
            return []
        hits = []
        for row in self.list_visible(user_id):
            if matches_query(query, row):
                hits.append(row)
            if len(hits) >= limit:
                break
        return hits

    def find_possible_duplicates(
        self,
        user_id: UUID,
        display_name: str,
        aliases: list[str] | None = None,
        *,
        public_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Catalog rows that are the same movement under a different spelling.

        Backs the 409 on create/publish (SB-454) — the guard the catalog
        migration promised but never got. `public_only` is for publish, where the
        question is whether the shared library already has this movement.
        """
        rows = self.list_visible(user_id)
        if public_only:
            rows = [r for r in rows if r.get("visibility") == "public"]
        return find_duplicate_candidates(display_name, aliases, rows)

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
        """Create a coach-owned exercise; the key is generated to stay unique.

        Slug uniqueness is not duplicate protection — it is what lets a second
        row for the same movement exist as ``pull_up_2``. The semantic guard is
        ``find_possible_duplicates``, enforced by the route before it gets here.
        """
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
    """Per-user workout templates (the coach's plan) + their blocks and items."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def _write_blocks_and_items(
        self,
        template_id: str,
        blocks: Sequence[dict[str, Any]],
        items: Sequence[dict[str, Any]],
        owner: dict[str, Any],
    ) -> None:
        """Insert a template's circuits, then its items pointing at them.

        Items arrive referencing blocks by `block_index` because on create the
        blocks have no ids yet (SB-527). Resolve that here — the index is a
        payload convenience and must never reach the database.
        """
        block_ids: list[str] = []
        if blocks:
            rows = [
                {**b, **owner, "template_id": template_id, "position": b.get("position", i)}
                for i, b in enumerate(blocks)
            ]
            created = self.supabase.table("template_blocks").insert(rows).execute()
            block_ids = [b["id"] for b in cast(list[dict[str, Any]], created.data)]

        if not items:
            return
        item_rows = []
        for it in items:
            row = {**it, **owner, "template_id": template_id}
            idx = row.pop("block_index", None)
            if idx is not None and idx < len(block_ids):
                row["block_id"] = block_ids[idx]
            item_rows.append(row)
        self.supabase.table("template_items").insert(item_rows).execute()

    def create(
        self, user_id: UUID, payload: dict[str, Any], athlete_id: UUID | None = None
    ) -> dict[str, Any]:
        items: Sequence[dict[str, Any]] = payload.pop("items", []) or []
        blocks: Sequence[dict[str, Any]] = payload.pop("blocks", []) or []
        owner = _owner_fields(user_id, athlete_id)
        row = self.supabase.table("workout_templates").insert({**payload, **owner}).execute()
        template = cast(list[dict[str, Any]], row.data)[0]
        self._write_blocks_and_items(template["id"], blocks, items, owner)
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
        blocks: Sequence[dict[str, Any]] | None = payload.pop("blocks", None)
        if payload:
            self.supabase.table("workout_templates").update(payload).eq(
                "id", str(template_id)
            ).execute()

        if items is not None:
            # Replace items and circuits together (simplest correct edit).
            # Blocks go after items so the FK from template_items is clear
            # first; ON DELETE SET NULL would otherwise strand memberships.
            self.supabase.table("template_items").delete().eq(
                "template_id", str(template_id)
            ).execute()
            self.supabase.table("template_blocks").delete().eq(
                "template_id", str(template_id)
            ).execute()
            self._write_blocks_and_items(
                str(template_id), blocks or [], items, _owner_fields(user_id, athlete_id)
            )

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

        blocks = (
            self.supabase.table("template_blocks")
            .select("*")
            .in_("template_id", ids)
            .order("position")
            .execute()
        )
        blocks_by_template: dict[str, list[dict[str, Any]]] = {}
        for b in cast(list[dict[str, Any]], blocks.data):
            blocks_by_template.setdefault(b["template_id"], []).append(b)
        for t in templates:
            t["blocks"] = blocks_by_template.get(t["id"], [])

        # Attach completion state (SB-334): a template is "done" when a logged
        # session references it. One batched query; keep the latest session_date
        # per template (session_date is 'YYYY-MM-DD', so string max = latest).
        sessions = (
            self.supabase.table("workout_sessions")
            .select("template_id, session_date")
            .in_("template_id", ids)
            .execute()
        )
        last_by_template: dict[str, str] = {}
        for s in cast(list[dict[str, Any]], sessions.data):
            tid, d = s.get("template_id"), s.get("session_date")
            if tid and d and (tid not in last_by_template or d > last_by_template[tid]):
                last_by_template[tid] = d
        for t in templates:
            last = last_by_template.get(t["id"])
            t["has_session"] = last is not None
            t["last_session_date"] = last
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
        blocks = (
            self.supabase.table("template_blocks")
            .select("*")
            .eq("template_id", str(template_id))
            .order("position")
            .execute()
        )
        template["blocks"] = cast(list[dict[str, Any]], blocks.data)
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
