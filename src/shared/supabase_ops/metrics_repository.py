"""Repositories for the generic metric tracking tables.

IMPORTANT: the backend connects with the Supabase **service-role key**, which
**bypasses RLS**. So every query here MUST scope by ``user_id`` itself —
the database policies are a second line of defence for direct anon-key access,
not the primary guard on these server-side calls.
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast
from uuid import UUID

from supabase import Client


class MetricTypesRepository:
    """Read-only access to the global metric catalog."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def list_all(self) -> list[dict[str, Any]]:
        result = self.supabase.table("metric_types").select("*").order("key").execute()
        return cast(list[dict[str, Any]], result.data)

    def get(self, key: str) -> dict[str, Any] | None:
        result = self.supabase.table("metric_types").select("*").eq("key", key).execute()
        data = cast(list[dict[str, Any]], result.data)
        return data[0] if data else None


class MetricEntriesRepository:
    """Per-user metric entry log."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def insert(self, user_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        row = {**payload, "user_id": str(user_id)}
        result = self.supabase.table("metric_entries").insert(row).execute()
        return cast(list[dict[str, Any]], result.data)[0]

    def list(
        self,
        user_id: UUID,
        metric_key: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        query = self.supabase.table("metric_entries").select("*").eq("user_id", str(user_id))
        if metric_key is not None:
            query = query.eq("metric_key", metric_key)
        if date_from is not None:
            query = query.gte("occurred_on", date_from.isoformat())
        if date_to is not None:
            query = query.lte("occurred_on", date_to.isoformat())
        result = query.order("occurred_on", desc=True).limit(limit).execute()
        return cast(list[dict[str, Any]], result.data)

    def delete(self, user_id: UUID, entry_id: UUID) -> bool:
        """Delete one entry, scoped to its owner. Returns True if a row went."""
        result = (
            self.supabase.table("metric_entries")
            .delete()
            .eq("id", str(entry_id))
            .eq("user_id", str(user_id))
            .execute()
        )
        return bool(cast(list[dict[str, Any]], result.data))


class MetricGoalsRepository:
    """Per-user native goals."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def create(self, user_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        row = {**payload, "user_id": str(user_id)}
        result = self.supabase.table("metric_goals").insert(row).execute()
        return cast(list[dict[str, Any]], result.data)[0]

    def list(self, user_id: UUID, status: str | None = None) -> list[dict[str, Any]]:
        query = self.supabase.table("metric_goals").select("*").eq("user_id", str(user_id))
        if status is not None:
            query = query.eq("status", status)
        result = query.order("created_at", desc=True).execute()
        return cast(list[dict[str, Any]], result.data)

    def get(self, user_id: UUID, goal_id: UUID) -> dict[str, Any] | None:
        result = (
            self.supabase.table("metric_goals")
            .select("*")
            .eq("id", str(goal_id))
            .eq("user_id", str(user_id))
            .execute()
        )
        data = cast(list[dict[str, Any]], result.data)
        return data[0] if data else None

    def update(
        self, user_id: UUID, goal_id: UUID, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not payload:
            return self.get(user_id, goal_id)
        result = (
            self.supabase.table("metric_goals")
            .update(payload)
            .eq("id", str(goal_id))
            .eq("user_id", str(user_id))
            .execute()
        )
        data = cast(list[dict[str, Any]], result.data)
        return data[0] if data else None

    def delete(self, user_id: UUID, goal_id: UUID) -> bool:
        result = (
            self.supabase.table("metric_goals")
            .delete()
            .eq("id", str(goal_id))
            .eq("user_id", str(user_id))
            .execute()
        )
        return bool(cast(list[dict[str, Any]], result.data))
