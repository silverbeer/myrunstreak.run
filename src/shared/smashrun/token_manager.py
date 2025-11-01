"""Token management for SmashRun OAuth with AWS Secrets Manager."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import ClientError

from .oauth import SmashRunOAuthClient

logger = logging.getLogger(__name__)


class TokenManager:
    """
    Manages SmashRun OAuth tokens with AWS Secrets Manager.

    Handles token storage, retrieval, and automatic refresh when expired.
    """

    def __init__(
        self,
        secret_name: str,
        oauth_client: SmashRunOAuthClient,
        region_name: str = "us-east-2",
    ) -> None:
        """
        Initialize token manager.

        Args:
            secret_name: AWS Secrets Manager secret name
            oauth_client: OAuth client for token refresh
            region_name: AWS region for Secrets Manager
        """
        self.secret_name = secret_name
        self.oauth_client = oauth_client
        self.region_name = region_name

        self._secrets_client = boto3.client(
            "secretsmanager",
            region_name=region_name
        )

    def get_tokens(self) -> dict[str, Any]:
        """
        Retrieve tokens from AWS Secrets Manager.

        Returns:
            Dictionary containing access_token, refresh_token, expires_at

        Raises:
            ClientError: If secret retrieval fails
        """
        logger.info(f"Retrieving tokens from secret: {self.secret_name}")

        try:
            response = self._secrets_client.get_secret_value(
                SecretId=self.secret_name
            )

            secret_data = json.loads(response["SecretString"])
            logger.info("Successfully retrieved tokens")
            return secret_data

        except ClientError as e:
            logger.error(f"Failed to retrieve tokens: {e}")
            raise

    def update_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int,
    ) -> None:
        """
        Update tokens in AWS Secrets Manager.

        Args:
            access_token: New access token
            refresh_token: New refresh token
            expires_in: Seconds until token expires

        Raises:
            ClientError: If secret update fails
        """
        logger.info(f"Updating tokens in secret: {self.secret_name}")

        # Calculate expiration timestamp
        expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

        secret_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "updated_at": datetime.utcnow().isoformat(),
        }

        try:
            self._secrets_client.update_secret(
                SecretId=self.secret_name,
                SecretString=json.dumps(secret_data)
            )
            logger.info("Successfully updated tokens")

        except ClientError as e:
            logger.error(f"Failed to update tokens: {e}")
            raise

    def get_valid_access_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.

        Automatically refreshes the token if it's expired or expiring soon.

        Returns:
            Valid access token

        Raises:
            ClientError: If token retrieval or refresh fails
        """
        logger.info("Getting valid access token")

        tokens = self.get_tokens()

        # Check if token needs refresh
        expires_at_str = tokens.get("expires_at")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            now = datetime.utcnow().replace(tzinfo=expires_at.tzinfo)

            # Refresh if expired or expiring within 1 day
            buffer = timedelta(days=1)
            if now + buffer >= expires_at:
                logger.info("Token expired or expiring soon, refreshing...")
                return self._refresh_and_update(tokens["refresh_token"])

        logger.info("Using existing access token")
        return tokens["access_token"]

    def _refresh_and_update(self, refresh_token: str) -> str:
        """
        Refresh access token and update stored tokens.

        Args:
            refresh_token: Current refresh token

        Returns:
            New access token

        Raises:
            Exception: If token refresh fails
        """
        logger.info("Refreshing access token")

        try:
            # Refresh token
            new_tokens = self.oauth_client.refresh_access_token(refresh_token)

            # Update stored tokens
            self.update_tokens(
                access_token=new_tokens["access_token"],
                refresh_token=new_tokens.get("refresh_token", refresh_token),
                expires_in=new_tokens["expires_in"],
            )

            logger.info("Successfully refreshed and updated tokens")
            return new_tokens["access_token"]

        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            raise

    def initialize_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int,
    ) -> None:
        """
        Initialize tokens in Secrets Manager (first-time setup).

        Args:
            access_token: Initial access token from OAuth flow
            refresh_token: Initial refresh token from OAuth flow
            expires_in: Seconds until token expires

        Raises:
            ClientError: If secret creation fails
        """
        logger.info(f"Initializing tokens in secret: {self.secret_name}")

        expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

        secret_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "created_at": datetime.utcnow().isoformat(),
        }

        try:
            # Try to create secret (will fail if exists)
            self._secrets_client.create_secret(
                Name=self.secret_name,
                Description="SmashRun OAuth tokens for MyRunStreak.com",
                SecretString=json.dumps(secret_data),
                Tags=[
                    {"Key": "Project", "Value": "MyRunStreak"},
                    {"Key": "Purpose", "Value": "SmashRunOAuth"},
                ],
            )
            logger.info("Successfully initialized tokens (created new secret)")

        except self._secrets_client.exceptions.ResourceExistsException:
            # Secret already exists, update it instead
            logger.info("Secret already exists, updating...")
            self.update_tokens(access_token, refresh_token, expires_in)

        except ClientError as e:
            logger.error(f"Failed to initialize tokens: {e}")
            raise
