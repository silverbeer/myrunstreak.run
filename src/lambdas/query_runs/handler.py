"""Lambda function handler for querying running statistics (multi-user)."""

import json
from datetime import date, timedelta
from typing import Any, cast
from uuid import UUID

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.shared.secrets import get_smashrun_oauth_credentials
from src.shared.smashrun import SmashRunAPIClient, SmashRunOAuthClient
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import (
    RunsRepository,
    TokenRepository,
    UsersRepository,
    activity_to_run_dict,
)

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
                "total_km": float(month["total_km"]),
                "avg_km": float(month["avg_km"]),
                "avg_pace_min_per_km": (
                    float(month["avg_pace"]) if month["avg_pace"] else None
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
        .select("start_year, start_month, run_count, total_km")
        .eq("user_id", str(user_id))
        .order("total_km", desc=True)
        .limit(1)
        .execute()
    )

    monthly_data = cast(list[dict[str, Any]], monthly_result.data)
    if monthly_data:
        monthly = monthly_data[0]
        records["most_km_month"] = {
            "month": f"{monthly['start_year']}-{monthly['start_month']:02d}-01",
            "run_count": monthly["run_count"],
            "total_km": float(monthly["total_km"]),
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


@app.post("/sync-user")
def sync_runs() -> dict[str, Any]:
    """
    Sync runs from SmashRun to Supabase.

    Query Parameters:
        user_id (required): User UUID

    Body (optional JSON):
        since: Date string (YYYY-MM-DD) - sync runs from this date
        until: Date string (YYYY-MM-DD) - sync runs until this date
        full: Boolean - if true, sync all runs (ignores since/until)

    Returns:
        Sync results with count of runs synced
    """
    user_id = get_user_id_from_request()
    logger.info(f"Starting sync for user {user_id}")

    # Parse request body
    body: dict[str, Any] = {}
    if app.current_event.body:
        try:
            body = json.loads(app.current_event.body)
        except json.JSONDecodeError:
            pass

    # Determine date range
    if body.get("full"):
        # Full sync - get all runs (use a very old date)
        since_date = date(2010, 1, 1)
        until_date = date.today()
        logger.info("Full sync requested")
    else:
        # Parse since date (default: last 7 days)
        since_str = body.get("since")
        if since_str:
            since_date = date.fromisoformat(since_str)
        else:
            since_date = date.today() - timedelta(days=7)

        # Parse until date (default: today)
        until_str = body.get("until")
        if until_str:
            until_date = date.fromisoformat(until_str)
        else:
            until_date = date.today()

    logger.info(f"Sync date range: {since_date} to {until_date}")

    # Initialize repositories
    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)
    token_repo = TokenRepository(supabase)

    # Get user's source ID
    source_id = token_repo.get_source_id_for_user(user_id, "smashrun")
    if not source_id:
        raise ValueError(f"No SmashRun source found for user {user_id}")

    # Get user's tokens from Supabase
    tokens = token_repo.get_user_tokens(user_id, "smashrun")
    if not tokens:
        raise ValueError(f"No tokens found for user {user_id}. Please authenticate first.")

    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Check if token needs refresh
    if token_repo.is_token_expired(user_id, "smashrun"):
        logger.info("Token expired, refreshing...")

        # Get SmashRun OAuth credentials from Secrets Manager
        smashrun_creds = get_smashrun_oauth_credentials()

        # Initialize OAuth client
        oauth_client = SmashRunOAuthClient(
            client_id=smashrun_creds.get("client_id", ""),
            client_secret=smashrun_creds.get("client_secret", ""),
            redirect_uri="urn:ietf:wg:oauth:2.0:oob",
        )

        # Refresh the token
        new_tokens = oauth_client.refresh_access_token(refresh_token)
        access_token = new_tokens["access_token"]
        new_refresh_token = new_tokens.get("refresh_token", refresh_token)

        # Save new tokens to Supabase
        token_repo.save_user_tokens(
            user_id=user_id,
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=new_tokens.get("expires_in"),
            source_type="smashrun",
        )

        logger.info("Token refreshed successfully")

    # Fetch and store runs
    runs_synced = 0

    with SmashRunAPIClient(access_token=access_token) as api_client:
        logger.info("Fetching activities from SmashRun")

        # Get activities in date range
        activities = api_client.get_all_activities_since(since_date)

        # Filter by until_date
        activities = [
            a for a in activities
            if date.fromisoformat(a.get("startDateTimeLocal", "")[:10]) <= until_date
        ]

        logger.info(f"Found {len(activities)} activities in date range")

        # Store each activity
        for activity_data in activities:
            try:
                # Parse activity
                activity = api_client.parse_activity(activity_data)

                # Convert to run dict
                run_data = activity_to_run_dict(activity, user_id, source_id)

                # Upsert (insert or update if exists)
                runs_repo.upsert_run(user_id, source_id, run_data)

                runs_synced += 1
                logger.debug(
                    f"Synced: {activity.start_date_time_local.date()} - "
                    f"{activity.distance:.2f} km"
                )

            except Exception as e:
                logger.error(f"Failed to process activity {activity_data.get('activityId')}: {e}")
                continue

    # Add metrics
    metrics.add_metric(name="RunsSynced", unit=MetricUnit.Count, value=runs_synced)

    logger.info(f"Sync completed: {runs_synced} runs")

    return {
        "message": "Sync completed",
        "runs_synced": runs_synced,
        "since": since_date.isoformat(),
        "until": until_date.isoformat(),
    }


@app.post("/auth/store-tokens")
def store_tokens() -> dict[str, Any]:
    """
    Store OAuth tokens for a user.

    Query Parameters:
        user_id (required): User UUID

    Body (JSON):
        access_token: OAuth access token (required)
        refresh_token: OAuth refresh token (required)
        expires_in: Token expiry in seconds (optional)

    Returns:
        Success message
    """
    user_id = get_user_id_from_request()
    logger.info(f"Storing tokens for user {user_id}")

    # Parse request body
    if not app.current_event.body:
        raise ValueError("Request body is required")

    try:
        body = json.loads(app.current_event.body)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in request body: {e}") from e

    # Validate required fields
    access_token = body.get("access_token")
    refresh_token = body.get("refresh_token")
    expires_in = body.get("expires_in")

    if not access_token:
        raise ValueError("access_token is required")
    if not refresh_token:
        raise ValueError("refresh_token is required")

    # Store tokens in Supabase
    supabase = get_supabase_client()
    token_repo = TokenRepository(supabase)

    token_repo.save_user_tokens(
        user_id=user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        source_type="smashrun",
    )

    logger.info(f"Tokens stored successfully for user {user_id}")

    return {
        "message": "Tokens stored successfully",
        "user_id": str(user_id),
    }


@app.get("/auth/login-url")
def get_login_url() -> dict[str, Any]:
    """
    Get SmashRun OAuth authorization URL.

    Query Parameters:
        redirect_uri (optional): Custom redirect URI (default: http://localhost:9876/callback)

    Returns:
        Authorization URL to redirect user to
    """
    # Get redirect URI from query params or use default
    redirect_uri = app.current_event.get_query_string_value(
        "redirect_uri", "http://localhost:9876/callback"
    )

    # Get SmashRun OAuth credentials from Secrets Manager
    smashrun_creds = get_smashrun_oauth_credentials()

    # Build authorization URL
    oauth_client = SmashRunOAuthClient(
        client_id=smashrun_creds.get("client_id", ""),
        client_secret=smashrun_creds.get("client_secret", ""),
        redirect_uri=redirect_uri,
    )

    auth_url = oauth_client.get_authorization_url(state="stk_cli")

    logger.info(f"Generated login URL with redirect_uri={redirect_uri}")

    return {
        "auth_url": auth_url,
        "redirect_uri": redirect_uri,
    }


@app.post("/auth/callback")
def handle_auth_callback() -> dict[str, Any]:
    """
    Handle OAuth callback - exchange code for tokens, register user, store tokens.

    Body (JSON):
        code: Authorization code from SmashRun (required)
        redirect_uri (optional): Redirect URI used in auth request

    Returns:
        User ID and username
    """
    # Parse request body
    if not app.current_event.body:
        raise ValueError("Request body is required")

    try:
        body = json.loads(app.current_event.body)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in request body: {e}") from e

    # Get authorization code
    code = body.get("code")
    if not code:
        raise ValueError("code is required")

    redirect_uri = body.get("redirect_uri", "http://localhost:9876/callback")

    logger.info("Processing OAuth callback")

    # Get SmashRun OAuth credentials from Secrets Manager
    smashrun_creds = get_smashrun_oauth_credentials()

    # Exchange code for tokens
    oauth_client = SmashRunOAuthClient(
        client_id=smashrun_creds.get("client_id", ""),
        client_secret=smashrun_creds.get("client_secret", ""),
        redirect_uri=redirect_uri,
    )

    token_data = oauth_client.exchange_code_for_token(code)
    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]
    expires_in = token_data.get("expires_in")

    logger.info("Token exchange successful")

    # Get SmashRun user info
    with SmashRunAPIClient(access_token=access_token) as api_client:
        user_info = api_client.get_user_info()
        username = user_info.get("userName", "unknown")
        smashrun_user_id = str(user_info.get("id", ""))

    logger.info(f"Got SmashRun user info: {username}")

    # Register/link user in Supabase
    supabase = get_supabase_client()
    users_repo = UsersRepository(supabase)
    token_repo = TokenRepository(supabase)

    user, created = users_repo.get_or_create_user_with_source(
        source_type="smashrun",
        source_username=username,
        source_user_id=smashrun_user_id,
        display_name=username,
    )

    user_id = UUID(user["user_id"])

    if created:
        logger.info(f"Created new user: {user_id}")
    else:
        logger.info(f"Linked existing user: {user_id}")

    # Store tokens in Supabase
    token_repo.save_user_tokens(
        user_id=user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        source_type="smashrun",
    )

    logger.info(f"Tokens stored for user {user_id}")

    return {
        "user_id": str(user_id),
        "username": username,
        "created": created,
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
