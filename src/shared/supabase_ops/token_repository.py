"""Repository for OAuth token management in Supabase."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from supabase import Client

logger = logging.getLogger(__name__)


class TokenRepository:
    """
    Repository for managing OAuth tokens stored in Supabase.

    Handles token storage, retrieval, and refresh for user data sources.
    """

    def __init__(self, supabase: Client):
        """
        Initialize repository with Supabase client.

        Args:
            supabase: Authenticated Supabase client
        """
        self.supabase = supabase

    def get_user_tokens(
        self, user_id: UUID, source_type: str = "smashrun"
    ) -> dict[str, Any] | None:
        """
        Get OAuth tokens for a user's source.

        Args:
            user_id: User UUID
            source_type: Source type (default: 'smashrun')

        Returns:
            Dict with access_token, refresh_token, token_expires_at, or None if not found
        """
        result = (
            self.supabase.table("user_sources")
            .select("id, access_token, refresh_token, token_expires_at")
            .eq("user_id", str(user_id))
            .eq("source_type", source_type)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        data_list = cast(list[dict[str, Any]], result.data)

        if not data_list:
            logger.debug(f"No {source_type} source found for user {user_id}")
            return None

        source = data_list[0]

        if not source.get("access_token"):
            logger.debug(f"No tokens stored for user {user_id} {source_type} source")
            return None

        return {
            "source_id": source["id"],
            "access_token": source["access_token"],
            "refresh_token": source["refresh_token"],
            "token_expires_at": source["token_expires_at"],
        }

    def save_user_tokens(
        self,
        user_id: UUID,
        access_token: str,
        refresh_token: str,
        expires_in: int | None = None,
        source_type: str = "smashrun",
    ) -> None:
        """
        Save OAuth tokens for a user's source.

        Args:
            user_id: User UUID
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_in: Token expiry in seconds (None = no expiration)
            source_type: Source type (default: 'smashrun')
        """
        token_expires_at = None
        if expires_in:
            token_expires_at = (datetime.now(UTC) + timedelta(seconds=expires_in)).isoformat()

        result = (
            self.supabase.table("user_sources")
            .update(
                {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_expires_at": token_expires_at,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            )
            .eq("user_id", str(user_id))
            .eq("source_type", source_type)
            .eq("is_active", True)
            .execute()
        )

        data_list = cast(list[dict[str, Any]], result.data)
        if data_list:
            logger.info(f"Updated tokens for user {user_id} {source_type} source")
        else:
            logger.warning(f"No {source_type} source found to update for user {user_id}")

    def is_token_expired(self, user_id: UUID, source_type: str = "smashrun") -> bool:
        """
        Check if user's access token is expired or will expire soon.

        Args:
            user_id: User UUID
            source_type: Source type (default: 'smashrun')

        Returns:
            True if token is expired or expires within 5 minutes
        """
        tokens = self.get_user_tokens(user_id, source_type)

        if not tokens:
            return True

        if not tokens.get("token_expires_at"):
            # No expiration set = not expired
            return False

        # Parse expiration time
        expires_at_str = tokens["token_expires_at"]
        if isinstance(expires_at_str, str):
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        else:
            expires_at = expires_at_str

        # Check if expired or will expire within 5 minutes
        buffer = timedelta(minutes=5)
        now = datetime.now(UTC)

        return now + buffer >= expires_at

    def get_valid_access_token(self, user_id: UUID, source_type: str = "smashrun") -> str | None:
        """
        Get a valid access token, refreshing if necessary.

        Note: This method only returns the token if it's valid.
        Actual token refresh requires the SmashRun OAuth client,
        which should be done in a higher-level service.

        Args:
            user_id: User UUID
            source_type: Source type (default: 'smashrun')

        Returns:
            Valid access token or None if refresh needed
        """
        tokens = self.get_user_tokens(user_id, source_type)

        if not tokens:
            return None

        if self.is_token_expired(user_id, source_type):
            logger.debug(f"Token expired for user {user_id}, refresh needed")
            return None

        access_token: str = tokens["access_token"]
        return access_token

    def get_source_id_for_user(self, user_id: UUID, source_type: str = "smashrun") -> UUID | None:
        """
        Get the source ID for a user's source.

        Args:
            user_id: User UUID
            source_type: Source type (default: 'smashrun')

        Returns:
            Source UUID or None if not found
        """
        result = (
            self.supabase.table("user_sources")
            .select("id")
            .eq("user_id", str(user_id))
            .eq("source_type", source_type)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        data_list = cast(list[dict[str, Any]], result.data)

        if not data_list:
            return None

        return UUID(data_list[0]["id"])

    def delete_tokens(self, user_id: UUID, source_type: str = "smashrun") -> None:
        """
        Delete/clear tokens for a user's source.

        Used when user disconnects or tokens become invalid.

        Args:
            user_id: User UUID
            source_type: Source type (default: 'smashrun')
        """
        self.supabase.table("user_sources").update(
            {
                "access_token": None,
                "refresh_token": None,
                "token_expires_at": None,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ).eq("user_id", str(user_id)).eq("source_type", source_type).execute()

        logger.info(f"Cleared tokens for user {user_id} {source_type} source")
