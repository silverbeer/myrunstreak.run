"""Repository pattern for run data operations."""

import logging
from datetime import date
from typing import Any

import duckdb  # type: ignore[import-not-found]

from ..models import Activity, Split

logger = logging.getLogger(__name__)


class RunRepository:
    """Repository for run data CRUD operations."""

    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        """
        Initialize repository with a DuckDB connection.

        Args:
            connection: Active DuckDB connection
        """
        self.connection = connection

    def insert_run(self, activity: Activity) -> None:
        """
        Insert a new run into the database.

        Args:
            activity: Activity model to insert

        Raises:
            duckdb.ConstraintException: If activity_id already exists
        """
        logger.info(f"Inserting run {activity.activity_id}")

        # Calculate derived fields
        start_date = activity.start_date_time_local.date()
        start_year = activity.start_date_time_local.year
        start_month = activity.start_date_time_local.month
        start_day_of_week = activity.start_date_time_local.weekday()

        self.connection.execute(
            """
            INSERT INTO runs (
                activity_id, external_id,
                start_date_time_local, start_date, start_year, start_month, start_day_of_week,
                distance_km, duration_seconds,
                average_pace_min_per_km, average_speed_kph,
                cadence_average, cadence_min, cadence_max,
                heart_rate_average, heart_rate_min, heart_rate_max,
                body_weight_kg, how_felt,
                terrain, temperature_celsius, weather_type, humidity_percent, wind_speed_kph,
                notes,
                activity_type, device_type, app_version,
                has_gps_data, has_heart_rate_data, has_cadence_data, has_laps
            ) VALUES (
                ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?, ?,
                ?,
                ?, ?, ?,
                ?, ?, ?, ?
            )
            """,
            [
                activity.activity_id,
                activity.external_id,
                activity.start_date_time_local,
                start_date,
                start_year,
                start_month,
                start_day_of_week,
                activity.distance,
                activity.duration,
                activity.average_pace_min_per_km,
                activity.average_speed_kph,
                activity.cadence_average,
                activity.cadence_min,
                activity.cadence_max,
                activity.heart_rate_average,
                activity.heart_rate_min,
                activity.heart_rate_max,
                activity.body_weight,
                activity.how_felt.value if activity.how_felt else None,
                activity.terrain.value if activity.terrain else None,
                activity.temperature,
                activity.weather_type.value if activity.weather_type else None,
                activity.humidity,
                activity.wind_speed,
                activity.notes,
                activity.activity_type.value,
                activity.external_device_type.value if activity.external_device_type else None,
                activity.external_app_version,
                activity.recording_keys is not None
                and any(k in ["latitude", "longitude"] for k in activity.recording_keys),
                activity.heart_rate_average is not None,
                activity.cadence_average is not None,
                activity.laps is not None and len(activity.laps) > 0,
            ],
        )

        self.connection.commit()
        logger.info(f"Successfully inserted run {activity.activity_id}")

    def upsert_run(self, activity: Activity) -> None:
        """
        Insert or update a run (upsert operation).

        Args:
            activity: Activity model to insert or update
        """
        try:
            self.insert_run(activity)
        except duckdb.ConstraintException:
            logger.info(f"Run {activity.activity_id} already exists, updating")
            self.update_run(activity)

    def update_run(self, activity: Activity) -> None:
        """
        Update an existing run.

        Args:
            activity: Activity model with updated data
        """
        logger.info(f"Updating run {activity.activity_id}")

        start_date = activity.start_date_time_local.date()
        start_year = activity.start_date_time_local.year
        start_month = activity.start_date_time_local.month
        start_day_of_week = activity.start_date_time_local.weekday()

        self.connection.execute(
            """
            UPDATE runs SET
                external_id = ?,
                start_date_time_local = ?, start_date = ?, start_year = ?, start_month = ?, start_day_of_week = ?,
                distance_km = ?, duration_seconds = ?,
                average_pace_min_per_km = ?, average_speed_kph = ?,
                cadence_average = ?, cadence_min = ?, cadence_max = ?,
                heart_rate_average = ?, heart_rate_min = ?, heart_rate_max = ?,
                body_weight_kg = ?, how_felt = ?,
                terrain = ?, temperature_celsius = ?, weather_type = ?, humidity_percent = ?, wind_speed_kph = ?,
                notes = ?,
                device_type = ?, app_version = ?,
                has_gps_data = ?, has_heart_rate_data = ?, has_cadence_data = ?, has_laps = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE activity_id = ?
            """,
            [
                activity.external_id,
                activity.start_date_time_local,
                start_date,
                start_year,
                start_month,
                start_day_of_week,
                activity.distance,
                activity.duration,
                activity.average_pace_min_per_km,
                activity.average_speed_kph,
                activity.cadence_average,
                activity.cadence_min,
                activity.cadence_max,
                activity.heart_rate_average,
                activity.heart_rate_min,
                activity.heart_rate_max,
                activity.body_weight,
                activity.how_felt.value if activity.how_felt else None,
                activity.terrain.value if activity.terrain else None,
                activity.temperature,
                activity.weather_type.value if activity.weather_type else None,
                activity.humidity,
                activity.wind_speed,
                activity.notes,
                activity.external_device_type.value if activity.external_device_type else None,
                activity.external_app_version,
                activity.recording_keys is not None
                and any(k in ["latitude", "longitude"] for k in activity.recording_keys),
                activity.heart_rate_average is not None,
                activity.cadence_average is not None,
                activity.laps is not None and len(activity.laps) > 0,
                activity.activity_id,
            ],
        )

        self.connection.commit()
        logger.info(f"Successfully updated run {activity.activity_id}")

    def get_run_by_id(self, activity_id: str) -> dict[str, Any] | None:
        """
        Retrieve a run by its activity ID.

        Args:
            activity_id: Unique activity identifier

        Returns:
            Run data as dictionary, or None if not found
        """
        result = self.connection.execute(
            "SELECT * FROM runs WHERE activity_id = ?",
            [activity_id],
        ).fetchone()

        if result is None:
            return None

        # Get column names
        columns = [desc[0] for desc in self.connection.description]
        return dict(zip(columns, result, strict=True))

    def get_runs_by_date_range(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        """
        Retrieve runs within a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of run data dictionaries
        """
        results = self.connection.execute(
            """
            SELECT * FROM runs
            WHERE start_date BETWEEN ? AND ?
            ORDER BY start_date DESC, start_date_time_local DESC
            """,
            [start_date, end_date],
        ).fetchall()

        columns = [desc[0] for desc in self.connection.description]
        return [dict(zip(columns, row, strict=True)) for row in results]

    def get_latest_run(self) -> dict[str, Any] | None:
        """
        Get the most recent run.

        Returns:
            Latest run data as dictionary, or None if no runs exist
        """
        result = self.connection.execute(
            """
            SELECT * FROM runs
            ORDER BY start_date_time_local DESC
            LIMIT 1
            """
        ).fetchone()

        if result is None:
            return None

        columns = [desc[0] for desc in self.connection.description]
        return dict(zip(columns, result, strict=True))

    def get_total_runs(self) -> int:
        """
        Get total number of runs in the database.

        Returns:
            Total run count
        """
        result = self.connection.execute("SELECT COUNT(*) FROM runs").fetchone()
        return result[0] if result else 0

    def get_current_streak(self) -> int:
        """
        Calculate the current consecutive running streak in days.

        Returns:
            Current streak length in days
        """
        result = self.connection.execute(
            """
            WITH RECURSIVE date_check AS (
                SELECT
                    CURRENT_DATE as check_date,
                    0 as days_back
                UNION ALL
                SELECT
                    check_date - INTERVAL '1 day',
                    days_back + 1
                FROM date_check
                WHERE
                    days_back < 365
                    AND EXISTS (
                        SELECT 1 FROM runs
                        WHERE start_date = check_date - INTERVAL '1 day'
                    )
            )
            SELECT MAX(days_back) as streak
            FROM date_check
            WHERE EXISTS (
                SELECT 1 FROM runs WHERE start_date = check_date
            )
            """
        ).fetchone()

        return result[0] if result and result[0] else 0

    def insert_splits(self, activity_id: str, splits: list[Split], unit: str = "mi") -> None:
        """
        Insert splits for a run.

        Args:
            activity_id: Activity ID these splits belong to
            splits: List of Split models
            unit: 'mi' for miles or 'km' for kilometers

        Raises:
            duckdb.ConstraintException: If splits already exist for this activity/unit
        """
        if not splits:
            logger.info(f"No splits to insert for activity {activity_id}")
            return

        logger.info(f"Inserting {len(splits)} {unit} splits for activity {activity_id}")

        for i, split in enumerate(splits, start=1):
            self.connection.execute(
                """
                INSERT INTO splits (
                    activity_id, split_number, split_unit,
                    cumulative_distance, cumulative_seconds,
                    speed_kph, heart_rate,
                    cumulative_elevation_gain_meters, cumulative_elevation_loss_meters
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    activity_id,
                    i,  # split_number
                    unit,
                    split.cumulative_distance,
                    split.cumulative_seconds,
                    split.speed_kph,
                    split.heart_rate,
                    split.cumulative_elevation_gain_meters,
                    split.cumulative_elevation_loss_meters,
                ],
            )

        logger.info(f"Successfully inserted {len(splits)} splits for activity {activity_id}")

    def delete_splits(self, activity_id: str, unit: str | None = None) -> None:
        """
        Delete splits for a run.

        Args:
            activity_id: Activity ID to delete splits for
            unit: Optional unit filter ('mi' or 'km'). If None, deletes all splits.
        """
        if unit:
            logger.info(f"Deleting {unit} splits for activity {activity_id}")
            self.connection.execute(
                "DELETE FROM splits WHERE activity_id = ? AND split_unit = ?",
                [activity_id, unit],
            )
        else:
            logger.info(f"Deleting all splits for activity {activity_id}")
            self.connection.execute(
                "DELETE FROM splits WHERE activity_id = ?",
                [activity_id],
            )

    def upsert_splits(self, activity_id: str, splits: list[Split], unit: str = "mi") -> None:
        """
        Insert or replace splits for a run.

        Args:
            activity_id: Activity ID these splits belong to
            splits: List of Split models
            unit: 'mi' for miles or 'km' for kilometers
        """
        logger.info(f"Upserting {len(splits)} {unit} splits for activity {activity_id}")

        # Delete existing splits for this activity/unit
        self.delete_splits(activity_id, unit)

        # Insert new splits
        self.insert_splits(activity_id, splits, unit)

        logger.info(f"Successfully upserted splits for activity {activity_id}")

    def has_splits(self, activity_id: str, unit: str = "mi") -> bool:
        """
        Check if splits exist for an activity.

        Args:
            activity_id: Activity ID to check
            unit: 'mi' for miles or 'km' for kilometers

        Returns:
            True if splits exist, False otherwise
        """
        result = self.connection.execute(
            "SELECT COUNT(*) FROM splits WHERE activity_id = ? AND split_unit = ?",
            [activity_id, unit],
        ).fetchone()

        return result[0] > 0 if result else False
