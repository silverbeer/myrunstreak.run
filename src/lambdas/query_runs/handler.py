"""Lambda function handler for querying running statistics."""

import json
import logging
import os
from datetime import date, timedelta
from typing import Any

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.shared.duckdb_ops import DuckDBManager

# Initialize Lambda Powertools
logger = Logger(service="myrunstreak-query")
metrics = Metrics(namespace="MyRunStreak", service="myrunstreak-query")

# API Gateway event handler
app = APIGatewayRestResolver()


@app.get("/stats/overall")
def get_overall_stats():
    """Get overall running statistics."""
    logger.info("Getting overall statistics")

    duckdb_path = os.getenv("DUCKDB_PATH", "s3://myrunstreak-data-dev-855323747881/runs.duckdb")
    db_manager = DuckDBManager(duckdb_path, read_only=True)

    with db_manager as conn:
        result = conn.execute("""
            SELECT
                COUNT(*) as total_runs,
                SUM(distance_km) as total_distance,
                AVG(distance_km) as avg_distance,
                MAX(distance_km) as longest_run,
                AVG(average_pace_min_per_km) as avg_pace
            FROM runs
        """).fetchone()

        if not result or result[0] == 0:
            return {
                "total_runs": 0,
                "total_km": 0,
                "avg_km": 0,
                "longest_run_km": 0,
                "avg_pace_min_per_km": 0
            }

        return {
            "total_runs": result[0],
            "total_km": round(result[1], 2) if result[1] else 0,
            "avg_km": round(result[2], 2) if result[2] else 0,
            "longest_run_km": round(result[3], 2) if result[3] else 0,
            "avg_pace_min_per_km": round(result[4], 2) if result[4] else 0
        }


@app.get("/runs/recent")
def get_recent_runs():
    """Get recent runs."""
    # Get query parameter for limit (default 10, max 100)
    limit = min(int(app.current_event.get_query_string_value("limit", "10")), 100)

    logger.info(f"Getting {limit} recent runs")

    duckdb_path = os.getenv("DUCKDB_PATH", "s3://myrunstreak-data-dev-855323747881/runs.duckdb")
    db_manager = DuckDBManager(duckdb_path, read_only=True)

    with db_manager as conn:
        results = conn.execute(f"""
            SELECT
                activity_id,
                start_date_time_local,
                distance_km,
                duration_seconds,
                average_pace_min_per_km,
                heart_rate_average,
                temperature_celsius,
                weather_type
            FROM runs
            ORDER BY start_date_time_local DESC
            LIMIT {limit}
        """).fetchall()

        runs = []
        for row in results:
            runs.append({
                "activity_id": row[0],
                "date": str(row[1]),
                "distance_km": round(row[2], 2) if row[2] else 0,
                "duration_seconds": row[3],
                "duration_minutes": round(row[3] / 60, 1) if row[3] else 0,
                "avg_pace_min_per_km": round(row[4], 2) if row[4] else 0,
                "heart_rate_avg": row[5],
                "temperature_celsius": row[6],
                "weather": row[7]
            })

        return {
            "count": len(runs),
            "runs": runs
        }


@app.get("/stats/monthly")
def get_monthly_stats():
    """Get monthly statistics."""
    # Get query parameter for limit (default 12 months)
    limit = min(int(app.current_event.get_query_string_value("limit", "12")), 60)

    logger.info(f"Getting {limit} months of statistics")

    duckdb_path = os.getenv("DUCKDB_PATH", "s3://myrunstreak-data-dev-855323747881/runs.duckdb")
    db_manager = DuckDBManager(duckdb_path, read_only=True)

    with db_manager as conn:
        results = conn.execute(f"""
            SELECT
                DATE_TRUNC('month', start_date_time_local)::DATE as month,
                COUNT(*) as run_count,
                SUM(distance_km) as total_distance,
                AVG(distance_km) as avg_distance,
                AVG(average_pace_min_per_km) as avg_pace
            FROM runs
            GROUP BY month
            ORDER BY month DESC
            LIMIT {limit}
        """).fetchall()

        months = []
        for row in results:
            months.append({
                "month": str(row[0]),
                "run_count": row[1],
                "total_km": round(row[2], 2) if row[2] else 0,
                "avg_km": round(row[3], 2) if row[3] else 0,
                "avg_pace_min_per_km": round(row[4], 2) if row[4] else 0
            })

        return {
            "count": len(months),
            "months": months
        }


@app.get("/stats/streaks")
def get_streaks():
    """Get running streak analysis."""
    logger.info("Calculating running streaks")

    duckdb_path = os.getenv("DUCKDB_PATH", "s3://myrunstreak-data-dev-855323747881/runs.duckdb")
    db_manager = DuckDBManager(duckdb_path, read_only=True)

    with db_manager as conn:
        # Calculate streaks using window functions
        results = conn.execute("""
            WITH daily_runs AS (
                SELECT DISTINCT start_date as run_date
                FROM runs
            ),
            streak_groups AS (
                SELECT
                    run_date,
                    run_date - ROW_NUMBER() OVER (ORDER BY run_date) * INTERVAL 1 DAY as streak_group
                FROM daily_runs
            ),
            streaks AS (
                SELECT
                    MIN(run_date) as streak_start,
                    MAX(run_date) as streak_end,
                    COUNT(*) as streak_length
                FROM streak_groups
                GROUP BY streak_group
            )
            SELECT
                streak_start,
                streak_end,
                streak_length,
                CASE
                    WHEN streak_end >= CURRENT_DATE - INTERVAL 1 DAY THEN true
                    ELSE false
                END as is_current
            FROM streaks
            ORDER BY streak_length DESC
            LIMIT 10
        """).fetchall()

        streaks = []
        for row in results:
            streaks.append({
                "start_date": str(row[0]),
                "end_date": str(row[1]),
                "length_days": row[2],
                "is_current": row[3]
            })

        # Find current streak
        current_streak = next((s for s in streaks if s["is_current"]), None)

        return {
            "current_streak": current_streak["length_days"] if current_streak else 0,
            "longest_streak": streaks[0]["length_days"] if streaks else 0,
            "top_streaks": streaks
        }


@app.get("/stats/records")
def get_records():
    """Get personal records."""
    logger.info("Getting personal records")

    duckdb_path = os.getenv("DUCKDB_PATH", "s3://myrunstreak-data-dev-855323747881/runs.duckdb")
    db_manager = DuckDBManager(duckdb_path, read_only=True)

    with db_manager as conn:
        # Longest run
        longest = conn.execute("""
            SELECT start_date_time_local::DATE, distance_km, activity_id
            FROM runs
            ORDER BY distance_km DESC
            LIMIT 1
        """).fetchone()

        # Fastest pace (for runs >= 5 km)
        fastest = conn.execute("""
            SELECT start_date_time_local::DATE, average_pace_min_per_km, distance_km, activity_id
            FROM runs
            WHERE distance_km >= 5
            ORDER BY average_pace_min_per_km ASC
            LIMIT 1
        """).fetchone()

        # Most distance in a week
        weekly = conn.execute("""
            WITH weekly_totals AS (
                SELECT
                    DATE_TRUNC('week', start_date_time_local)::DATE as week_start,
                    SUM(distance_km) as total_distance
                FROM runs
                GROUP BY week_start
            )
            SELECT week_start, total_distance
            FROM weekly_totals
            ORDER BY total_distance DESC
            LIMIT 1
        """).fetchone()

        # Most distance in a month
        monthly = conn.execute("""
            WITH monthly_totals AS (
                SELECT
                    DATE_TRUNC('month', start_date_time_local)::DATE as month_start,
                    COUNT(*) as run_count,
                    SUM(distance_km) as total_distance
                FROM runs
                GROUP BY month_start
            )
            SELECT month_start, run_count, total_distance
            FROM monthly_totals
            ORDER BY total_distance DESC
            LIMIT 1
        """).fetchone()

        records = {}

        if longest:
            records["longest_run"] = {
                "date": str(longest[0]),
                "distance_km": round(longest[1], 2),
                "activity_id": longest[2]
            }

        if fastest:
            records["fastest_pace"] = {
                "date": str(fastest[0]),
                "pace_min_per_km": round(fastest[1], 2),
                "distance_km": round(fastest[2], 2),
                "activity_id": fastest[3]
            }

        if weekly:
            records["most_km_week"] = {
                "week_start": str(weekly[0]),
                "total_km": round(weekly[1], 2)
            }

        if monthly:
            records["most_km_month"] = {
                "month": str(monthly[0]),
                "run_count": monthly[1],
                "total_km": round(monthly[2], 2)
            }

        return records


@app.get("/runs")
def list_runs():
    """List all runs with pagination."""
    # Get query parameters
    offset = int(app.current_event.get_query_string_value("offset", "0"))
    limit = min(int(app.current_event.get_query_string_value("limit", "50")), 100)

    logger.info(f"Listing runs (offset={offset}, limit={limit})")

    duckdb_path = os.getenv("DUCKDB_PATH", "s3://myrunstreak-data-dev-855323747881/runs.duckdb")
    db_manager = DuckDBManager(duckdb_path, read_only=True)

    with db_manager as conn:
        # Get total count
        total = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

        # Get paginated results
        results = conn.execute(f"""
            SELECT
                activity_id,
                start_date_time_local,
                distance_km,
                duration_seconds,
                average_pace_min_per_km
            FROM runs
            ORDER BY start_date_time_local DESC
            LIMIT {limit}
            OFFSET {offset}
        """).fetchall()

        runs = []
        for row in results:
            runs.append({
                "activity_id": row[0],
                "date": str(row[1]),
                "distance_km": round(row[2], 2) if row[2] else 0,
                "duration_minutes": round(row[3] / 60, 1) if row[3] else 0,
                "avg_pace_min_per_km": round(row[4], 2) if row[4] else 0
            })

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "count": len(runs),
            "runs": runs
        }


@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """
    Lambda handler for query API.

    Uses Lambda Powertools API Gateway resolver to handle routing.
    """
    try:
        return app.resolve(event, context)
    except Exception as e:
        logger.exception(f"Query failed: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Internal server error",
                "message": str(e)
            })
        }
