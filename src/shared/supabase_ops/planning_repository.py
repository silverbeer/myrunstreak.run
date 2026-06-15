"""Repositories for the adaptive planning tables (SB-164).

plan_constraints / plan_days / readiness_log. Like the metric repos, the backend
connects with the service-role key (bypasses RLS), so every query scopes by
``user_id`` itself — the DB policies are a second line of defence.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any, cast
from uuid import UUID

from supabase import Client


class PlanConstraintsRepository:
    """Per-user known-in-advance limits (travel cap, injury window)."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def create(self, user_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        row = {**payload, "user_id": str(user_id)}
        result = self.supabase.table("plan_constraints").insert(row).execute()
        return cast(list[dict[str, Any]], result.data)[0]

    def list(
        self,
        user_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        query = self.supabase.table("plan_constraints").select("*").eq("user_id", str(user_id))
        # Overlap with [date_from, date_to]: starts on/before the window end and
        # ends on/after the window start.
        if date_to is not None:
            query = query.lte("start_on", date_to.isoformat())
        if date_from is not None:
            query = query.gte("end_on", date_from.isoformat())
        result = query.order("start_on").execute()
        return cast(list[dict[str, Any]], result.data)

    def delete(self, user_id: UUID, constraint_id: UUID) -> bool:
        result = (
            self.supabase.table("plan_constraints")
            .delete()
            .eq("id", str(constraint_id))
            .eq("user_id", str(user_id))
            .execute()
        )
        return bool(cast(list[dict[str, Any]], result.data))


class ReadinessRepository:
    """Per-user daily how-I-feel signal (one row per day; upserted)."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    def upsert(self, user_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        row = {**payload, "user_id": str(user_id)}
        result = (
            self.supabase.table("readiness_log").upsert(row, on_conflict="user_id,log_on").execute()
        )
        return cast(list[dict[str, Any]], result.data)[0]

    def list(
        self,
        user_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        query = self.supabase.table("readiness_log").select("*").eq("user_id", str(user_id))
        if date_from is not None:
            query = query.gte("log_on", date_from.isoformat())
        if date_to is not None:
            query = query.lte("log_on", date_to.isoformat())
        result = query.order("log_on").execute()
        return cast(list[dict[str, Any]], result.data)


class PlanDaysRepository:
    """Per-user generated prescriptions (the derived cache)."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    # Defined before ``list`` so its ``list[...]`` annotations resolve to the
    # builtin, not this class's ``list`` method (Python binds the method name
    # only once its ``def`` executes).
    def replace_from(
        self, user_id: UUID, from_date: date, rows: Sequence[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Delete this user's prescriptions on/after ``from_date`` and insert ``rows``.

        Past rows (before ``from_date``) are preserved as the record of what was
        asked. ``rows`` already carry their own ``plan_on`` (all >= ``from_date``).
        """
        self.supabase.table("plan_days").delete().eq("user_id", str(user_id)).gte(
            "plan_on", from_date.isoformat()
        ).execute()
        if not rows:
            return []
        payload = [{**r, "user_id": str(user_id)} for r in rows]
        result = self.supabase.table("plan_days").insert(payload).execute()
        return cast(list[dict[str, Any]], result.data)

    def list(
        self,
        user_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        query = self.supabase.table("plan_days").select("*").eq("user_id", str(user_id))
        if date_from is not None:
            query = query.gte("plan_on", date_from.isoformat())
        if date_to is not None:
            query = query.lte("plan_on", date_to.isoformat())
        result = query.order("plan_on").execute()
        return cast(list[dict[str, Any]], result.data)
