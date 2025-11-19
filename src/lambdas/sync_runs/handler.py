"""Lambda function handler for multi-user SmashRun sync."""

from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.shared.config import get_settings
from src.shared.smashrun import SmashRunAPIClient, SmashRunOAuthClient
from src.shared.smashrun.token_manager import TokenManager
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import (
    RunsRepository,
    UsersRepository,
    activity_to_run_dict,
)

# Initialize Lambda Powertools
logger = Logger(service="smashrun-sync")
metrics = Metrics(namespace="MyRunStreak", service="smashrun-sync")


@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """
    Lambda handler for multi-user SmashRun sync.

    Iterates over all active user sources and syncs runs from SmashRun API
    to Supabase PostgreSQL.

    Args:
        event: Lambda event (from EventBridge schedule)
        context: Lambda context

    Returns:
        Response with sync results for all users
    """
    logger.info("Starting multi-user SmashRun sync")

    try:
        # Load settings
        settings = get_settings()

        # Initialize Supabase client
        supabase = get_supabase_client()
        users_repo = UsersRepository(supabase)
        runs_repo = RunsRepository(supabase)

        # Get all active SmashRun sources
        logger.info("Fetching all active SmashRun sources")
        active_sources = users_repo.get_all_active_sources(source_type="smashrun")
        logger.info(f"Found {len(active_sources)} active source(s)")

        if not active_sources:
            logger.warning("No active sources found")
            return {
                "statusCode": 200,
                "body": {
                    "message": "No active sources to sync",
                    "total_runs_synced": 0,
                    "sources_synced": 0,
                },
            }

        # Sync each user source
        total_runs_synced = 0
        sources_synced = 0
        failed_sources = 0

        for source in active_sources:
            try:
                user_id = UUID(source["user_id"])
                source_id = UUID(source["id"])
                source_type = source["source_type"]
                access_token_secret = source["access_token_secret"]

                logger.info(f"Syncing source {source_id} (user={user_id}, type={source_type})")

                # Get last sync date (default to 30 days ago if never synced)
                last_sync_at = source.get("last_sync_at")
                if last_sync_at:
                    since_date = datetime.fromisoformat(last_sync_at).date()
                    logger.info(f"Last sync: {since_date}")
                else:
                    since_date = date.today() - timedelta(days=30)
                    logger.info(f"Never synced, using default: {since_date}")

                # Sync runs for this user source
                runs_synced = sync_user_source(
                    user_id=user_id,
                    source_id=source_id,
                    access_token_secret=access_token_secret,
                    since_date=since_date,
                    runs_repo=runs_repo,
                    settings=settings,
                )

                # Update last sync timestamp
                users_repo.update_source_last_sync(source_id)

                total_runs_synced += runs_synced
                sources_synced += 1

                logger.info(f"Successfully synced source {source_id}: {runs_synced} runs")

            except Exception as e:
                logger.exception(f"Failed to sync source {source.get('id')}: {e}")
                failed_sources += 1
                # Continue with next source
                continue

        # Add metrics
        metrics.add_metric(name="TotalRunsSynced", unit=MetricUnit.Count, value=total_runs_synced)
        metrics.add_metric(name="SourcesSynced", unit=MetricUnit.Count, value=sources_synced)
        metrics.add_metric(name="SourcesFailed", unit=MetricUnit.Count, value=failed_sources)
        metrics.add_metric(name="SyncSuccess", unit=MetricUnit.Count, value=1)

        logger.info(f"Sync completed: {total_runs_synced} runs from {sources_synced} sources")

        return {
            "statusCode": 200,
            "body": {
                "message": "Multi-user sync completed",
                "total_runs_synced": total_runs_synced,
                "sources_synced": sources_synced,
                "sources_failed": failed_sources,
            },
        }

    except Exception as e:
        logger.exception(f"Multi-user sync failed: {e}")

        # Add failure metric
        metrics.add_metric(name="SyncFailures", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "body": {
                "message": "Multi-user sync failed",
                "error": str(e),
            },
        }


def sync_user_source(
    user_id: UUID,
    source_id: UUID,
    access_token_secret: str,
    since_date: date,
    runs_repo: RunsRepository,
    settings: Any,
) -> int:
    """
    Sync runs for a single user source.

    Args:
        user_id: User UUID
        source_id: User source UUID
        access_token_secret: AWS Secrets Manager path for OAuth tokens
        since_date: Fetch runs on or after this date
        runs_repo: RunsRepository for storing runs
        settings: Application settings

    Returns:
        Number of runs synced

    Raises:
        Exception: If sync fails
    """
    logger.info(f"Syncing runs since {since_date} for source {source_id}")

    runs_synced = 0

    # Initialize OAuth client for token refresh
    oauth_client = SmashRunOAuthClient(
        client_id=settings.smashrun_client_id,
        client_secret=settings.smashrun_client_secret,
        redirect_uri=settings.smashrun_redirect_uri,
    )

    # Get valid access token (handles refresh if needed)
    token_manager = TokenManager(
        secret_name=access_token_secret,
        oauth_client=oauth_client,
        region_name=settings.aws_region,
    )

    access_token = token_manager.get_valid_access_token()
    logger.info("Retrieved valid access token")

    # Fetch and store runs
    with SmashRunAPIClient(access_token=access_token) as api_client:
        logger.info("Fetching user info")
        user_info = api_client.get_user_info()
        logger.info(f"Authenticated as: {user_info.get('userName')}")

        # Fetch all activities since last sync
        logger.info(f"Fetching activities since {since_date}")
        activities = api_client.get_all_activities_since(since_date)
        logger.info(f"Found {len(activities)} activities")

        # Store in Supabase
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
                    f"{activity.distance:.2f} km - "
                    f"{activity.activity_id}"
                )

            except Exception as e:
                logger.error(f"Failed to process activity {activity_data.get('activityId')}: {e}")
                # Continue with next activity
                continue

    logger.info(f"Successfully synced {runs_synced} runs for source {source_id}")
    return runs_synced
