"""Lambda function handler for querying running statistics (multi-user)."""

import json
from typing import Any, cast
from uuid import UUID

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import RunsRepository

# Initialize Lambda Powertools
logger = Logger(service="myrunstreak-query")
metrics = Metrics(namespace="MyRunStreak", service="myrunstreak-query")

# API Gateway event handler
app = APIGatewayRestResolver()


def get_user_id_from_request() -> UUID:
    """
    Extract user_id from request.

    For now, expects user_id as a query parameter.
    In production, this would come from JWT token or API key.

    Returns:
        User UUID

    Raises:
        ValueError: If user_id is missing or invalid
    """
    user_id_str = app.current_event.get_query_string_value("user_id")

    if not user_id_str:
        raise ValueError("user_id query parameter is required")

    try:
        return UUID(user_id_str)
    except ValueError as e:
        raise ValueError(f"Invalid user_id format: {user_id_str}") from e


@app.get("/stats/overall")
def get_overall_stats() -> dict[str, Any]:
    """
    Get overall running statistics for a user.

    Query Parameters:
        user_id (required): User UUID

    Returns:
        Overall statistics including total runs, distance, avg pace, etc.
    """
    user_id = get_user_id_from_request()
    logger.info(f"Getting overall statistics for user {user_id}")

    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)

    stats = runs_repo.get_user_overall_stats(user_id)

    return stats


@app.get("/runs/recent")
def get_recent_runs() -> dict[str, Any]:
    """
    Get recent runs for a user.

    Query Parameters:
        user_id (required): User UUID
        limit (optional): Number of runs to return (default 10, max 100)

    Returns:
        Recent runs with detailed information
    """
    user_id = get_user_id_from_request()

    # Get query parameter for limit (default 10, max 100)
    limit = min(int(app.current_event.get_query_string_value("limit", "10")), 100)

    logger.info(f"Getting {limit} recent runs for user {user_id}")

    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)

    # Get runs from repository
    runs_data = runs_repo.get_runs_by_user(user_id, limit=limit, offset=0)

    # Format response
    runs = []
    for run in runs_data:
        runs.append(
            {
                "activity_id": run["source_activity_id"],
                "date": run["start_date_time_local"],
                "distance_km": float(run["distance_km"]),
                "duration_seconds": float(run["duration_seconds"]),
                "duration_minutes": round(float(run["duration_seconds"]) / 60, 1),
                "avg_pace_min_per_km": (
                    float(run["average_pace_min_per_km"])
                    if run["average_pace_min_per_km"]
                    else None
                ),
                "heart_rate_avg": run.get("heart_rate_average"),
                "temperature_celsius": run.get("temperature_celsius"),
                "weather": run.get("weather_type"),
            }
        )

    return {"count": len(runs), "runs": runs}


@app.get("/stats/monthly")
def get_monthly_stats() -> dict[str, Any]:
    """
    Get monthly statistics for a user.

    Query Parameters:
        user_id (required): User UUID
        limit (optional): Number of months to return (default 12, max 60)

    Returns:
        Monthly statistics using the monthly_summary view
    """
    user_id = get_user_id_from_request()

    # Get query parameter for limit (default 12 months)
    limit = min(int(app.current_event.get_query_string_value("limit", "12")), 60)

    logger.info(f"Getting {limit} months of statistics for user {user_id}")

    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)

    # Get monthly stats from repository
    monthly_data = runs_repo.get_monthly_stats(user_id, limit=limit)

    # Format response
    months = []
    for month in monthly_data:
        months.append(
            {
                "month": f"{month['start_year']}-{month['start_month']:02d}-01",
                "run_count": month["run_count"],
                "total_km": float(month["total_distance_km"]),
                "avg_km": float(month["avg_distance_km"]),
                "avg_pace_min_per_km": (
                    float(month["avg_pace_min_per_km"]) if month["avg_pace_min_per_km"] else None
                ),
            }
        )

    return {"count": len(months), "months": months}


@app.get("/stats/streaks")
def get_streaks() -> dict[str, Any]:
    """
    Get running streak analysis for a user.

    Query Parameters:
        user_id (required): User UUID

    Returns:
        Current streak, longest streak, and top streaks
    """
    user_id = get_user_id_from_request()
    logger.info(f"Calculating running streaks for user {user_id}")

    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)

    # Get current streak
    current_streak = runs_repo.get_current_streak(user_id)

    # For now, return simplified streak data
    # TODO: Implement full streak analysis (top streaks, longest streak)
    return {
        "current_streak": current_streak,
        "longest_streak": current_streak,  # Placeholder
        "top_streaks": [
            {
                "start_date": None,  # TODO
                "end_date": None,  # TODO
                "length_days": current_streak,
                "is_current": True,
            }
        ]
        if current_streak > 0
        else [],
    }


@app.get("/stats/records")
def get_records() -> dict[str, Any]:
    """
    Get personal records for a user.

    Query Parameters:
        user_id (required): User UUID

    Returns:
        Personal records (longest run, fastest pace, weekly/monthly bests)
    """
    user_id = get_user_id_from_request()
    logger.info(f"Getting personal records for user {user_id}")

    supabase = get_supabase_client()

    records = {}

    # Longest run
    longest_result = (
        supabase.table("runs")
        .select("start_date, distance_km, source_activity_id")
        .eq("user_id", str(user_id))
        .order("distance_km", desc=True)
        .limit(1)
        .execute()
    )

    longest_data = cast(list[dict[str, Any]], longest_result.data)
    if longest_data:
        longest = longest_data[0]
        records["longest_run"] = {
            "date": longest["start_date"],
            "distance_km": float(longest["distance_km"]),
            "activity_id": longest["source_activity_id"],
        }

    # Fastest pace (for runs >= 5 km)
    fastest_result = (
        supabase.table("runs")
        .select("start_date, average_pace_min_per_km, distance_km, source_activity_id")
        .eq("user_id", str(user_id))
        .gte("distance_km", 5)
        .order("average_pace_min_per_km", desc=False)
        .limit(1)
        .execute()
    )

    fastest_data = cast(list[dict[str, Any]], fastest_result.data)
    if fastest_data:
        fastest = fastest_data[0]
        records["fastest_pace"] = {
            "date": fastest["start_date"],
            "pace_min_per_km": float(fastest["average_pace_min_per_km"]),
            "distance_km": float(fastest["distance_km"]),
            "activity_id": fastest["source_activity_id"],
        }

    # Weekly and monthly bests using the views
    # Most distance in a month
    monthly_result = (
        supabase.table("monthly_summary")
        .select("start_year, start_month, run_count, total_distance_km")
        .eq("user_id", str(user_id))
        .order("total_distance_km", desc=True)
        .limit(1)
        .execute()
    )

    monthly_data = cast(list[dict[str, Any]], monthly_result.data)
    if monthly_data:
        monthly = monthly_data[0]
        records["most_km_month"] = {
            "month": f"{monthly['start_year']}-{monthly['start_month']:02d}-01",
            "run_count": monthly["run_count"],
            "total_km": float(monthly["total_distance_km"]),
        }

    # Note: Weekly bests would require a similar view (not implemented yet)
    # For now, we can add it later if needed

    return records


@app.get("/runs")
def list_runs() -> dict[str, Any]:
    """
    List all runs for a user with pagination.

    Query Parameters:
        user_id (required): User UUID
        offset (optional): Offset for pagination (default 0)
        limit (optional): Number of runs to return (default 50, max 100)

    Returns:
        Paginated list of runs
    """
    user_id = get_user_id_from_request()

    # Get query parameters
    offset = int(app.current_event.get_query_string_value("offset", "0"))
    limit = min(int(app.current_event.get_query_string_value("limit", "50")), 100)

    logger.info(f"Listing runs for user {user_id} (offset={offset}, limit={limit})")

    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)

    # Get runs from repository
    runs_data = runs_repo.get_runs_by_user(user_id, limit=limit, offset=offset)

    # Get total count
    total_result = (
        supabase.table("runs").select("*", count="exact").eq("user_id", str(user_id)).execute()  # type: ignore[arg-type]
    )
    total = total_result.count if total_result.count else 0

    # Format response
    runs = []
    for run in runs_data:
        runs.append(
            {
                "activity_id": run["source_activity_id"],
                "date": run["start_date_time_local"],
                "distance_km": float(run["distance_km"]),
                "duration_minutes": round(float(run["duration_seconds"]) / 60, 1),
                "avg_pace_min_per_km": (
                    float(run["average_pace_min_per_km"])
                    if run["average_pace_min_per_km"]
                    else None
                ),
            }
        )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "count": len(runs),
        "runs": runs,
    }


@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """
    Lambda handler for multi-user query API.

    Uses Lambda Powertools API Gateway resolver to handle routing.
    All endpoints require user_id query parameter.
    """
    try:
        return app.resolve(event, context)
    except ValueError as e:
        # Handle validation errors (missing user_id, etc.)
        logger.warning(f"Validation error: {e}")
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Bad request", "message": str(e)}),
        }
    except Exception as e:
        logger.exception(f"Query failed: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error", "message": str(e)}),
        }
