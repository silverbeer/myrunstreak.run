"""Repository for running goals in Supabase."""

import logging
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID

from supabase import Client

from ..models import Goal

logger = logging.getLogger(__name__)


class GoalsRepository:
    """
    Repository for yearly/monthly running goal data.

    Handles caching logic: yearly and monthly goals have different staleness
    thresholds to avoid re-fetching the same goal every sync.
    """

    def __init__(self, supabase: Client):
        """
        Initialize repository with Supabase client.

        Args:
            supabase: Authenticated Supabase client
        """
        self.supabase = supabase

    def get_by_period(
        self,
        user_id: UUID,
        source_id: UUID,
        year: int,
        month: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Get the stored goal row for a specific period.

        Args:
            user_id: User UUID
            source_id: Source UUID
            year: Goal year
            month: Goal month (1-12) or None for yearly goal

        Returns:
            Goal row dict, or None if not stored
        """
        query = (
            self.supabase.table("goals")
            .select("*")
            .eq("user_id", str(user_id))
            .eq("source_id", str(source_id))
            .eq("year", year)
        )
        query = query.is_("month", "null") if month is None else query.eq("month", month)

        result = query.execute()
        data_list = cast(list[dict[str, Any]], result.data)
        return data_list[0] if data_list else None

    def is_stale(
        self,
        row: dict[str, Any] | None,
        max_age: timedelta,
        now: datetime | None = None,
    ) -> bool:
        """
        Check whether a stored goal row needs refreshing.

        A missing row is considered stale (needs fetch). A row older than
        max_age is also stale.

        Args:
            row: Stored goal row (or None if absent)
            max_age: Staleness threshold
            now: Current time for testing (defaults to datetime.now with tz)

        Returns:
            True if the row should be refreshed
        """
        if row is None:
            return True

        fetched_at_raw = row.get("fetched_at")
        if not fetched_at_raw:
            return True

        fetched_at = datetime.fromisoformat(str(fetched_at_raw).replace("Z", "+00:00"))
        current = now or datetime.now(fetched_at.tzinfo)
        return (current - fetched_at) > max_age

    def upsert(
        self,
        user_id: UUID,
        source_id: UUID,
        goal: Goal,
    ) -> dict[str, Any]:
        """
        Insert or update a goal row.

        Uniqueness is enforced by partial unique indexes on
        (user_id, source_id, year) WHERE month IS NULL
        and (user_id, source_id, year, month) WHERE month IS NOT NULL.

        Args:
            user_id: User UUID
            source_id: Source UUID
            goal: Goal model with data fetched from source API

        Returns:
            Inserted/updated goal row
        """
        existing = self.get_by_period(user_id, source_id, goal.year, goal.month)
        now_iso = datetime.now(tz=goal.fetched_at.tzinfo if goal.fetched_at else None).isoformat()

        payload: dict[str, Any] = {
            "user_id": str(user_id),
            "source_id": str(source_id),
            "year": goal.year,
            "month": goal.month,
            "goal_text": goal.goal_text,
            "goal_km": goal.goal_km,
            "progress_km": goal.progress_km,
            "fetched_at": now_iso,
        }

        if existing:
            result = self.supabase.table("goals").update(payload).eq("id", existing["id"]).execute()
        else:
            result = self.supabase.table("goals").insert(payload).execute()

        data_list = cast(list[dict[str, Any]], result.data)
        logger.debug(f"Upserted goal for user {user_id} year={goal.year} month={goal.month}")
        return data_list[0]

    def mark_absent(
        self,
        user_id: UUID,
        source_id: UUID,
        year: int,
        month: int | None,
    ) -> dict[str, Any]:
        """
        Record that no goal is set for a period (API returned null).

        Stores a row with null goal_km so we don't re-fetch immediately.

        Args:
            user_id: User UUID
            source_id: Source UUID
            year: Goal year
            month: Goal month (or None for yearly)

        Returns:
            Inserted/updated row
        """
        placeholder = Goal(year=year, month=month)
        return self.upsert(user_id, source_id, placeholder)
