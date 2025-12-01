"""Repository for runs/activities data operations in Supabase."""

import logging
from datetime import date
from typing import Any, cast
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
            data_list = cast(list[dict[str, Any]], result.data)

            return data_list[0]

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
        data_list = cast(list[dict[str, Any]], result.data)

        return data_list[0] if data_list else None

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

        return cast(list[dict[str, Any]], result.data)

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
            .limit(10000)  # Override PostgREST default of 1000
            .execute()
        )

        return cast(list[dict[str, Any]], result.data)

    def get_user_overall_stats(self, user_id: UUID) -> dict[str, Any]:
        """
        Get overall running statistics for a user.

        Uses database-level aggregation via RPC to avoid PostgREST row limits.

        Args:
            user_id: User UUID

        Returns:
            Dict with total_runs, total_km, avg_km, longest_run_km, avg_pace
        """
        try:
            # Use database function for server-side aggregation
            result = self.supabase.rpc("get_user_stats", {"p_user_id": str(user_id)}).execute()

            if result.data:
                stats = result.data
                # Handle both direct dict and list responses
                if isinstance(stats, list) and len(stats) > 0:
                    stats = stats[0]
                return {
                    "total_runs": int(stats.get("total_runs", 0)),
                    "total_km": float(stats.get("total_km", 0)),
                    "avg_km": float(stats.get("avg_km", 0)),
                    "longest_run_km": float(stats.get("longest_run_km", 0)),
                    "avg_pace_min_per_km": float(stats.get("avg_pace_min_per_km", 0)),
                }
        except Exception as e:
            logger.warning(f"RPC get_user_stats failed, falling back to client-side: {e}")

        # Fallback to client-side aggregation (limited to 1000 rows)
        result = (
            self.supabase.table("runs")
            .select("distance_km, average_pace_min_per_km")
            .eq("user_id", str(user_id))
            .limit(10000)
            .execute()
        )

        runs = cast(list[dict[str, Any]], result.data)

        if not runs or len(runs) == 0:
            return {
                "total_runs": 0,
                "total_km": 0,
                "avg_km": 0,
                "longest_run_km": 0,
                "avg_pace_min_per_km": 0,
            }

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

        return cast(list[dict[str, Any]], result.data)

    def get_current_streak(self, user_id: UUID) -> int:
        """
        Get the user's current running streak (consecutive days).

        Uses database function to avoid row limits and ensure accurate count.

        Args:
            user_id: User UUID

        Returns:
            Number of consecutive days with runs (0 if no current streak)
        """
        try:
            # Use database function for accurate streak calculation
            result = self.supabase.rpc(
                "get_current_streak", {"p_user_id": str(user_id)}
            ).execute()

            if result.data is not None:
                return int(result.data)
        except Exception as e:
            logger.warning(f"RPC get_current_streak failed, falling back: {e}")

        # Fallback to client-side calculation (limited to 1000 rows)
        result = (
            self.supabase.table("runs")
            .select("start_date")
            .eq("user_id", str(user_id))
            .order("start_date", desc=True)
            .limit(10000)
            .execute()
        )

        data_list = cast(list[dict[str, Any]], result.data)

        if not data_list:
            return 0

        run_dates = {date.fromisoformat(row["start_date"]) for row in data_list}
        current_date = date.today()
        streak = 0

        if current_date not in run_dates:
            current_date = date.fromordinal(current_date.toordinal() - 1)
            if current_date not in run_dates:
                return 0

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
        data_list = cast(list[dict[str, Any]], result.data)

        return data_list[0]

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

        return cast(list[dict[str, Any]], result.data)

    def delete_run(self, run_id: UUID) -> None:
        """
        Delete a run and all related data (cascades to splits, laps, etc.).

        Args:
            run_id: Run UUID
        """
        self.supabase.table("runs").delete().eq("id", str(run_id)).execute()
        logger.info(f"Deleted run {run_id}")

    def recalculate_user_stats(self, user_id: UUID) -> dict[str, Any]:
        """
        Recalculate and store all running statistics for a user.

        Calls the database function to aggregate stats and store them in
        user_running_stats table. This avoids row limits for users with
        large datasets (e.g., multi-year streaks).

        Args:
            user_id: User UUID

        Returns:
            Dict with calculated statistics

        Raises:
            Exception: If recalculation fails
        """
        try:
            result = self.supabase.rpc(
                "recalculate_user_stats", {"p_user_id": str(user_id)}
            ).execute()

            if result.data:
                stats = result.data
                # Handle both direct dict and list responses
                if isinstance(stats, list) and len(stats) > 0:
                    stats = stats[0]
                stats_dict = cast(dict[str, Any], stats)
                logger.info(
                    f"Recalculated stats for user {user_id}: "
                    f"{stats_dict.get('lifetime_runs')} runs, "
                    f"{stats_dict.get('current_streak_days')} day streak"
                )
                return stats_dict

            return {}

        except Exception as e:
            logger.error(f"Failed to recalculate stats for user {user_id}: {e}")
            raise

    def get_user_running_stats(self, user_id: UUID) -> dict[str, Any] | None:
        """
        Get pre-calculated running statistics for a user.

        Fetches from the user_running_stats aggregation table. If no stats
        exist yet, returns None (caller should trigger recalculation).

        Args:
            user_id: User UUID

        Returns:
            Dict with all pre-calculated stats, or None if not found
        """
        result = (
            self.supabase.table("user_running_stats")
            .select("*")
            .eq("user_id", str(user_id))
            .execute()
        )

        data_list = cast(list[dict[str, Any]], result.data)
        return data_list[0] if data_list else None
