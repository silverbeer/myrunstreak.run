"""Repository for runs/activities data operations in Supabase."""

import logging
from datetime import date
from typing import Any
from uuid import UUID

from supabase import Client

logger = logging.getLogger(__name__)


class RunsRepository:
    """
    Repository for running activity data operations.

    Handles all CRUD operations for runs, splits, and related data.
    """

    def __init__(self, supabase: Client):
        """
        Initialize repository with Supabase client.

        Args:
            supabase: Authenticated Supabase client
        """
        self.supabase = supabase

    def upsert_run(
        self, user_id: UUID, source_id: UUID, run_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Insert or update a run.

        Uses ON CONFLICT to handle duplicates based on (user_id, source_id, source_activity_id).

        Args:
            user_id: User UUID
            source_id: Source UUID (user_sources.id)
            run_data: Run data dictionary (mapped from Activity model)

        Returns:
            Inserted/updated run record

        Raises:
            Exception: If upsert fails
        """
        # Add user_id and source_id
        run_data["user_id"] = str(user_id)
        run_data["source_id"] = str(source_id)

        try:
            result = (
                self.supabase.table("runs")
                .upsert(run_data, on_conflict="user_id,source_id,source_activity_id")
                .execute()
            )

            logger.debug(f"Upserted run {run_data.get('source_activity_id')} for user {user_id}")

            return result.data[0]

        except Exception as e:
            logger.error(f"Failed to upsert run {run_data.get('source_activity_id')}: {e}")
            raise

    def get_run_by_id(self, run_id: UUID) -> dict[str, Any] | None:
        """
        Get a run by its UUID.

        Args:
            run_id: Run UUID

        Returns:
            Run record or None if not found
        """
        result = self.supabase.table("runs").select("*").eq("id", str(run_id)).execute()

        return result.data[0] if result.data else None

    def get_runs_by_user(
        self, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """
        Get runs for a specific user with pagination.

        Args:
            user_id: User UUID
            limit: Maximum number of runs to return
            offset: Number of runs to skip

        Returns:
            List of run records
        """
        result = (
            self.supabase.table("runs")
            .select("*")
            .eq("user_id", str(user_id))
            .order("start_date_time_local", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return result.data

    def get_runs_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """
        Get runs within a date range for a user.

        Args:
            user_id: User UUID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of run records
        """
        result = (
            self.supabase.table("runs")
            .select("*")
            .eq("user_id", str(user_id))
            .gte("start_date", start_date.isoformat())
            .lte("start_date", end_date.isoformat())
            .order("start_date_time_local", desc=True)
            .execute()
        )

        return result.data

    def get_user_overall_stats(self, user_id: UUID) -> dict[str, Any]:
        """
        Get overall running statistics for a user.

        Uses client-side aggregation for now (PostgREST doesn't support aggregate functions).
        TODO: Create stored procedure for server-side aggregation.

        Args:
            user_id: User UUID

        Returns:
            Dict with total_runs, total_km, avg_km, longest_run_km, avg_pace
        """
        # Get all runs for user (we'll aggregate client-side)
        result = (
            self.supabase.table("runs")
            .select("distance_km, average_pace_min_per_km")
            .eq("user_id", str(user_id))
            .execute()
        )

        if not result.data or len(result.data) == 0:
            return {
                "total_runs": 0,
                "total_km": 0,
                "avg_km": 0,
                "longest_run_km": 0,
                "avg_pace_min_per_km": 0,
            }

        # Client-side aggregation
        runs = result.data
        total_runs = len(runs)
        distances = [float(r["distance_km"]) for r in runs]
        paces = [
            float(r["average_pace_min_per_km"])
            for r in runs
            if r["average_pace_min_per_km"] is not None
        ]

        return {
            "total_runs": total_runs,
            "total_km": round(sum(distances), 2),
            "avg_km": round(sum(distances) / total_runs, 2) if total_runs > 0 else 0,
            "longest_run_km": round(max(distances), 2) if distances else 0,
            "avg_pace_min_per_km": round(sum(paces) / len(paces), 2) if paces else 0,
        }

    def get_monthly_stats(self, user_id: UUID, limit: int = 12) -> list[dict[str, Any]]:
        """
        Get monthly statistics for a user using the monthly_summary view.

        Args:
            user_id: User UUID
            limit: Number of months to return

        Returns:
            List of monthly summary records
        """
        result = (
            self.supabase.table("monthly_summary")
            .select("*")
            .eq("user_id", str(user_id))
            .order("start_year", desc=True)
            .order("start_month", desc=True)
            .limit(limit)
            .execute()
        )

        return result.data

    def get_current_streak(self, user_id: UUID) -> int:
        """
        Get the user's current running streak (consecutive days).

        Uses a simple approach: count consecutive days backwards from today.

        Args:
            user_id: User UUID

        Returns:
            Number of consecutive days with runs (0 if no current streak)
        """
        # Get all distinct run dates in descending order
        result = (
            self.supabase.table("runs")
            .select("start_date")
            .eq("user_id", str(user_id))
            .order("start_date", desc=True)
            .execute()
        )

        if not result.data:
            return 0

        # Convert to set of dates for fast lookup
        run_dates = {date.fromisoformat(row["start_date"]) for row in result.data}

        # Count consecutive days from today
        current_date = date.today()
        streak = 0

        while current_date in run_dates:
            streak += 1
            current_date = date.fromordinal(current_date.toordinal() - 1)

        return streak

    def upsert_split(self, run_id: UUID, split_data: dict[str, Any]) -> dict[str, Any]:
        """
        Insert or update a split for a run.

        Args:
            run_id: Run UUID
            split_data: Split data dictionary

        Returns:
            Inserted/updated split record
        """
        split_data["run_id"] = str(run_id)

        result = (
            self.supabase.table("splits")
            .upsert(split_data, on_conflict="run_id,split_unit,split_number")
            .execute()
        )

        return result.data[0]

    def get_splits_for_run(self, run_id: UUID) -> list[dict[str, Any]]:
        """
        Get all splits for a run.

        Args:
            run_id: Run UUID

        Returns:
            List of split records
        """
        result = (
            self.supabase.table("splits")
            .select("*")
            .eq("run_id", str(run_id))
            .order("split_number")
            .execute()
        )

        return result.data

    def delete_run(self, run_id: UUID) -> None:
        """
        Delete a run and all related data (cascades to splits, laps, etc.).

        Args:
            run_id: Run UUID
        """
        self.supabase.table("runs").delete().eq("id", str(run_id)).execute()
        logger.info(f"Deleted run {run_id}")
