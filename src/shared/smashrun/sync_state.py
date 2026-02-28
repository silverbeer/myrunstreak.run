"""Sync state management for tracking last sync timestamp."""

import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class SyncStateManager:
    """
    Manages sync state to track when runs were last synced from SmashRun.

    Stores state in AWS Secrets Manager for persistence across Lambda invocations.
    """

    def __init__(
        self,
        secret_name: str = "myrunstreak/sync-state",
        region_name: str = "us-east-2",
    ) -> None:
        """
        Initialize sync state manager.

        Args:
            secret_name: AWS Secrets Manager secret name for sync state
            region_name: AWS region for Secrets Manager
        """
        self.secret_name = secret_name
        self.region_name = region_name

        self._secrets_client = boto3.client("secretsmanager", region_name=region_name)

    def get_last_sync_date(self) -> date:
        """
        Get the date of the last successful sync.

        Returns:
            Date of last sync, or 30 days ago if never synced

        """
        logger.info(f"Retrieving last sync date from: {self.secret_name}")

        try:
            response = self._secrets_client.get_secret_value(SecretId=self.secret_name)

            state_data = json.loads(response["SecretString"])
            last_sync_str = state_data.get("last_sync_date")

            if last_sync_str:
                last_sync = date.fromisoformat(last_sync_str)
                logger.info(f"Last sync date: {last_sync}")
                return last_sync
            else:
                # No last sync date, default to 30 days ago
                default_date = date.today() - timedelta(days=30)
                logger.info(f"No last sync date found, using default: {default_date}")
                return default_date

        except self._secrets_client.exceptions.ResourceNotFoundException:
            # Secret doesn't exist yet, default to 30 days ago
            default_date = date.today() - timedelta(days=30)
            logger.info(f"Sync state secret not found, using default: {default_date}")
            return default_date

        except ClientError as e:
            logger.error(f"Failed to retrieve sync state: {e}")
            # Return safe default on error
            return date.today() - timedelta(days=30)

    def update_last_sync_date(
        self,
        sync_date: date,
        runs_synced: int = 0,
    ) -> None:
        """
        Update the last successful sync date.

        Args:
            sync_date: Date to record as last sync
            runs_synced: Number of runs synced in this batch

        Raises:
            ClientError: If state update fails
        """
        logger.info(f"Updating last sync date to: {sync_date}")

        state_data = {
            "last_sync_date": sync_date.isoformat(),
            "last_sync_timestamp": datetime.now(UTC).isoformat(),
            "runs_synced": runs_synced,
        }

        try:
            # Try to update existing secret
            self._secrets_client.update_secret(
                SecretId=self.secret_name, SecretString=json.dumps(state_data)
            )
            logger.info(f"Successfully updated sync state ({runs_synced} runs)")

        except self._secrets_client.exceptions.ResourceNotFoundException:
            # Secret doesn't exist, create it
            logger.info("Creating new sync state secret")
            self._create_sync_state(state_data)

        except ClientError as e:
            logger.error(f"Failed to update sync state: {e}")
            raise

    def _create_sync_state(self, state_data: dict[str, Any]) -> None:
        """
        Create initial sync state secret.

        Args:
            state_data: State data to store

        Raises:
            ClientError: If secret creation fails
        """
        try:
            self._secrets_client.create_secret(
                Name=self.secret_name,
                Description="MyRunStreak.com sync state tracking",
                SecretString=json.dumps(state_data),
                Tags=[
                    {"Key": "Project", "Value": "MyRunStreak"},
                    {"Key": "Purpose", "Value": "SyncState"},
                ],
            )
            logger.info("Successfully created sync state secret")

        except ClientError as e:
            logger.error(f"Failed to create sync state secret: {e}")
            raise

    def record_sync_attempt(
        self,
        success: bool,
        runs_synced: int = 0,
        error_message: str | None = None,
    ) -> None:
        """
        Record a sync attempt (for monitoring/debugging).

        Args:
            success: Whether sync succeeded
            runs_synced: Number of runs synced
            error_message: Error message if sync failed
        """
        if success:
            logger.info(f"Sync succeeded: {runs_synced} runs synced")
            # Update last sync date to today
            self.update_last_sync_date(date.today(), runs_synced)
        else:
            logger.error(f"Sync failed: {error_message}")
            # Don't update last sync date on failure
