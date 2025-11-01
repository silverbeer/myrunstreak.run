"""Lambda function handler for daily SmashRun sync."""

import logging
from datetime import date
from typing import Any

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.shared.config import get_settings
from src.shared.duckdb_ops import DuckDBManager, RunRepository
from src.shared.smashrun import SmashRunAPIClient, SmashRunOAuthClient
from src.shared.smashrun.sync_state import SyncStateManager
from src.shared.smashrun.token_manager import TokenManager

# Initialize Lambda Powertools
logger = Logger(service="smashrun-sync")
tracer = Tracer(service="smashrun-sync")
metrics = Metrics(namespace="MyRunStreak", service="smashrun-sync")


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """
    Lambda handler for daily SmashRun sync.

    Fetches runs from SmashRun API since last sync and stores in DuckDB on S3.

    Args:
        event: Lambda event (from EventBridge schedule)
        context: Lambda context

    Returns:
        Response with sync results
    """
    logger.info("Starting SmashRun sync")

    try:
        # Load settings
        settings = get_settings()

        # Initialize managers
        oauth_client = SmashRunOAuthClient(
            client_id=settings.smashrun_client_id,
            client_secret=settings.smashrun_client_secret,
            redirect_uri=settings.smashrun_redirect_uri,
        )

        # Get secret names from environment (set by Terraform)
        import os
        smashrun_secret_name = os.getenv("SMASHRUN_SECRET_NAME", "myrunstreak/dev/smashrun/oauth")

        # Derive sync state secret name from SmashRun secret name
        # e.g., "myrunstreak/dev/smashrun/oauth" -> "myrunstreak/dev/sync-state"
        sync_state_secret = smashrun_secret_name.rsplit("/", 2)[0] + "/sync-state"

        token_manager = TokenManager(
            secret_name=smashrun_secret_name,
            oauth_client=oauth_client,
            region_name=settings.aws_region,
        )

        # Sync state manager will create its secret if it doesn't exist
        sync_state_manager = SyncStateManager(
            secret_name=sync_state_secret,
            region_name=settings.aws_region,
        )

        # Get valid access token (auto-refreshes if needed)
        logger.info("Getting valid access token")
        access_token = token_manager.get_valid_access_token()
        metrics.add_metric(name="TokenRefreshes", unit=MetricUnit.Count, value=1)

        # Get last sync date
        last_sync_date = sync_state_manager.get_last_sync_date()
        logger.info(f"Last sync date: {last_sync_date}")

        # Fetch runs from SmashRun
        runs_synced = sync_runs(
            access_token=access_token,
            since_date=last_sync_date,
            duckdb_path=settings.duckdb_path,
        )

        # Record successful sync
        sync_state_manager.record_sync_attempt(
            success=True,
            runs_synced=runs_synced,
        )

        # Add metrics
        metrics.add_metric(name="RunsSynced", unit=MetricUnit.Count, value=runs_synced)
        metrics.add_metric(name="SyncSuccess", unit=MetricUnit.Count, value=1)

        logger.info(f"Sync completed successfully: {runs_synced} runs synced")

        return {
            "statusCode": 200,
            "body": {
                "message": "Sync completed successfully",
                "runs_synced": runs_synced,
                "since_date": last_sync_date.isoformat(),
            },
        }

    except Exception as e:
        logger.exception(f"Sync failed: {e}")

        # Record failed sync
        try:
            sync_state_manager.record_sync_attempt(
                success=False,
                error_message=str(e),
            )
        except Exception:
            pass  # Don't fail if we can't record the failure

        # Add failure metric
        metrics.add_metric(name="SyncFailures", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "body": {
                "message": "Sync failed",
                "error": str(e),
            },
        }


@tracer.capture_method
def sync_runs(
    access_token: str,
    since_date: date,
    duckdb_path: str,
) -> int:
    """
    Sync runs from SmashRun to DuckDB.

    Args:
        access_token: Valid SmashRun access token
        since_date: Fetch runs on or after this date
        duckdb_path: Path to DuckDB database (local or S3)

    Returns:
        Number of runs synced

    Raises:
        Exception: If sync fails
    """
    logger.info(f"Syncing runs since {since_date} to {duckdb_path}")

    runs_synced = 0

    # Initialize database
    db_manager = DuckDBManager(duckdb_path)

    # Check if schema exists, initialize if needed
    if not db_manager.table_exists("runs"):
        logger.info("Initializing database schema")
        db_manager.initialize_schema()

    # Fetch and store runs
    with SmashRunAPIClient(access_token=access_token) as api_client:
        logger.info("Fetching user info")
        user_info = api_client.get_user_info()
        logger.info(f"Authenticated as: {user_info.get('userName')}")

        # Fetch all activities since last sync
        logger.info(f"Fetching activities since {since_date}")
        activities = api_client.get_all_activities_since(since_date)
        logger.info(f"Found {len(activities)} activities")

        # Store in database
        with db_manager as conn:
            repo = RunRepository(conn)

            for activity_data in activities:
                try:
                    # Parse activity
                    activity = api_client.parse_activity(activity_data)

                    # Upsert (insert or update if exists)
                    repo.upsert_run(activity)

                    runs_synced += 1
                    logger.info(
                        f"Synced: {activity.start_date_time_local.date()} - "
                        f"{activity.distance_miles:.2f} mi - "
                        f"{activity.activity_id}"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to process activity {activity_data.get('activityId')}: {e}"
                    )
                    # Continue with next activity
                    continue

    logger.info(f"Successfully synced {runs_synced} runs")
    return runs_synced
