"""Lambda handler for publishing run status to GCS."""

import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from google.cloud import storage
from google.oauth2 import service_account

from src.shared.secrets import get_secret
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops.runs_repository import RunsRepository
from src.shared.supabase_ops.users_repository import UsersRepository

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
GCS_BUCKET_NAME = "myrunstreak-public"
GCS_OBJECT_PATH = "status.json"
ENVIRONMENT = "dev"

# Conversion factor
KM_TO_MILES = 0.621371


def km_to_miles(km: float) -> float:
    """Convert kilometers to miles."""
    return km * KM_TO_MILES


def get_gcs_credentials() -> dict[str, Any]:
    """Get GCS service account credentials from Secrets Manager."""
    secret_name = f"myrunstreak/{ENVIRONMENT}/gcs/credentials"
    # get_secret already returns parsed JSON as a dict
    return get_secret(secret_name)


def upload_to_gcs(data: dict[str, Any]) -> str:
    """
    Upload JSON data to Google Cloud Storage.

    Args:
        data: Dictionary to upload as JSON

    Returns:
        Public URL of uploaded file
    """
    # Get credentials from Secrets Manager
    creds_dict = get_gcs_credentials()
    credentials = service_account.Credentials.from_service_account_info(creds_dict)

    # Create GCS client
    client = storage.Client(credentials=credentials, project=creds_dict.get("project_id"))

    # Upload to bucket
    bucket = client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(GCS_OBJECT_PATH)

    # Set cache control
    blob.cache_control = "public, max-age=300"  # Cache for 5 minutes

    # Upload with explicit content type
    json_data = json.dumps(data, indent=2, default=str)
    blob.upload_from_string(json_data, content_type="application/json")

    logger.info(f"Uploaded status to gs://{GCS_BUCKET_NAME}/{GCS_OBJECT_PATH}")

    return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{GCS_OBJECT_PATH}"


def build_status_data(user_id: UUID, runs_repo: RunsRepository) -> dict[str, Any]:
    """
    Build the status JSON structure.

    Args:
        user_id: User UUID
        runs_repo: Runs repository instance

    Returns:
        Status data dictionary
    """
    today = date.today()
    seven_days_ago = today - timedelta(days=7)

    # Get last 7 days of runs
    recent_runs = runs_repo.get_runs_by_date_range(user_id, seven_days_ago, today)

    # Get current streak
    streak_days = runs_repo.get_current_streak(user_id)

    # Determine if ran today
    ran_today = any(run["start_date"] == today.isoformat() for run in recent_runs)

    # Get last run (most recent)
    last_run = None
    if recent_runs:
        latest = recent_runs[0]  # Already sorted desc by date
        distance_mi = km_to_miles(float(latest["distance_km"]))
        last_run = {
            "date": latest["start_date"],
            "distance_mi": round(distance_mi, 2),
            "duration_min": round(float(latest["duration_seconds"]) / 60, 1),
        }

    # Build last 7 days array (in miles)
    last_7_days = []
    for run in recent_runs:
        distance_mi = km_to_miles(float(run["distance_km"]))
        last_7_days.append(
            {
                "date": run["start_date"],
                "distance_mi": round(distance_mi, 2),
            }
        )

    # Calculate streak start date (approximate)
    streak_start = None
    if streak_days > 0:
        streak_start = (today - timedelta(days=streak_days - 1)).isoformat()

    # Calculate total miles during the streak
    streak_total_km = 0.0
    if streak_days > 0 and streak_start:
        streak_start_date = date.fromisoformat(streak_start)
        streak_runs = runs_repo.get_runs_by_date_range(user_id, streak_start_date, today)
        streak_total_km = sum(float(run["distance_km"]) for run in streak_runs)
    streak_total_mi = round(km_to_miles(streak_total_km), 1)

    # Get runs for this month
    first_of_month = today.replace(day=1)
    month_runs = runs_repo.get_runs_by_date_range(user_id, first_of_month, today)
    month_total_km = sum(float(run["distance_km"]) for run in month_runs)
    month_total_mi = round(km_to_miles(month_total_km), 1)

    # Get runs for this year
    first_of_year = today.replace(month=1, day=1)
    year_runs = runs_repo.get_runs_by_date_range(user_id, first_of_year, today)
    year_total_km = sum(float(run["distance_km"]) for run in year_runs)
    year_total_mi = round(km_to_miles(year_total_km), 1)

    return {
        "updated_at": datetime.now(UTC).isoformat(),
        "ran_today": ran_today,
        "streak": {
            "current_days": streak_days,
            "started": streak_start,
            "total_mi": streak_total_mi,
        },
        "last_run": last_run,
        "last_7_days": last_7_days,
        "month_total_mi": month_total_mi,
        "year_total_mi": year_total_mi,
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for publishing run status.

    Can be triggered by:
    - EventBridge schedule
    - Direct invocation from sync Lambda
    - API Gateway (for testing)

    Args:
        event: Lambda event (may contain user_id override)
        context: Lambda context

    Returns:
        Response with status URL
    """
    logger.info(f"Publish status event: {json.dumps(event)}")

    try:
        # Initialize clients
        supabase = get_supabase_client()
        runs_repo = RunsRepository(supabase)
        users_repo = UsersRepository(supabase)

        # Get user_id from event or use default (first active SmashRun user)
        user_id_str = event.get("user_id")

        if not user_id_str:
            # Get first active SmashRun source as default
            sources = users_repo.get_all_active_sources(source_type="smashrun")
            if not sources:
                raise ValueError("No active SmashRun sources found")
            user_id = UUID(sources[0]["user_id"])
            logger.info(f"Using default user_id from first active source: {user_id}")
        else:
            user_id = UUID(user_id_str)

        # Build status data
        status_data = build_status_data(user_id, runs_repo)

        # Upload to GCS
        public_url = upload_to_gcs(status_data)

        logger.info(f"Published status for user {user_id}: {public_url}")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Status published successfully",
                    "url": public_url,
                    "ran_today": status_data["ran_today"],
                    "streak_days": status_data["streak"]["current_days"],
                }
            ),
        }

    except Exception as e:
        logger.error(f"Failed to publish status: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
