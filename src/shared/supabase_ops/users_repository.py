"""Repository for users and data sources operations in Supabase."""

import logging
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from supabase import Client

logger = logging.getLogger(__name__)


class UsersRepository:
    """
    Repository for user and data source operations.

    Handles user accounts and their connected data sources (SmashRun, Strava, etc.).
    """

    def __init__(self, supabase: Client):
        """
        Initialize repository with Supabase client.

        Args:
            supabase: Authenticated Supabase client
        """
        self.supabase = supabase

    def create_user(
        self, email: str | None = None, display_name: str | None = None
    ) -> dict[str, Any]:
        """
        Create a new user.

        Args:
            email: User email (optional for now)
            display_name: Display name

        Returns:
            Created user record with generated user_id
        """
        data = {}
        if email:
            data["email"] = email
        if display_name:
            data["display_name"] = display_name

        result = self.supabase.table("users").insert(data).execute()
        data_list = cast(list[dict[str, Any]], result.data)

        logger.info(f"Created user {data_list[0]['user_id']}")

        return data_list[0]

    def get_user_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        """
        Get user by UUID.

        Args:
            user_id: User UUID

        Returns:
            User record or None if not found
        """
        result = self.supabase.table("users").select("*").eq("user_id", str(user_id)).execute()
        data_list = cast(list[dict[str, Any]], result.data)

        return data_list[0] if data_list else None

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """
        Get user by email.

        Args:
            email: User email

        Returns:
            User record or None if not found
        """
        result = self.supabase.table("users").select("*").eq("email", email).execute()
        data_list = cast(list[dict[str, Any]], result.data)

        return data_list[0] if data_list else None

    def create_user_source(
        self,
        user_id: UUID,
        source_type: str,
        access_token_secret: str,
        source_user_id: str | None = None,
        source_username: str | None = None,
    ) -> dict[str, Any]:
        """
        Connect a data source to a user.

        Args:
            user_id: User UUID
            source_type: Source type (smashrun, strava, etc.)
            access_token_secret: AWS Secrets Manager path for OAuth tokens
            source_user_id: User ID in the source system
            source_username: Username in the source system

        Returns:
            Created user_source record
        """
        data = {
            "user_id": str(user_id),
            "source_type": source_type,
            "access_token_secret": access_token_secret,
            "source_user_id": source_user_id,
            "source_username": source_username,
        }

        result = self.supabase.table("user_sources").insert(data).execute()
        data_list = cast(list[dict[str, Any]], result.data)

        logger.info(f"Connected {source_type} source for user {user_id}: {data_list[0]['id']}")

        return data_list[0]

    def get_user_sources(self, user_id: UUID, active_only: bool = True) -> list[dict[str, Any]]:
        """
        Get all data sources for a user.

        Args:
            user_id: User UUID
            active_only: If True, only return active sources

        Returns:
            List of user_source records
        """
        query = self.supabase.table("user_sources").select("*").eq("user_id", str(user_id))

        if active_only:
            query = query.eq("is_active", True)

        result = query.execute()

        return cast(list[dict[str, Any]], result.data)

    def get_source_by_id(self, source_id: UUID) -> dict[str, Any] | None:
        """
        Get a specific data source.

        Args:
            source_id: Source UUID

        Returns:
            User_source record or None if not found
        """
        result = self.supabase.table("user_sources").select("*").eq("id", str(source_id)).execute()
        data_list = cast(list[dict[str, Any]], result.data)

        return data_list[0] if data_list else None

    def update_source_sync_status(
        self,
        source_id: UUID,
        last_sync_at: datetime,
        last_sync_status: str = "success",
    ) -> None:
        """
        Update source sync timestamp and status.

        Args:
            source_id: Source UUID
            last_sync_at: Timestamp of last sync
            last_sync_status: Status (success, failed, in_progress)
        """
        self.supabase.table("user_sources").update(
            {
                "last_sync_at": last_sync_at.isoformat(),
                "last_sync_status": last_sync_status,
            }
        ).eq("id", str(source_id)).execute()

    def update_source_last_sync(self, source_id: UUID) -> None:
        """
        Update source last sync timestamp to now.

        Convenience method for marking successful sync completion.

        Args:
            source_id: Source UUID
        """
        self.update_source_sync_status(source_id, datetime.utcnow(), last_sync_status="success")

    def get_all_active_sources(self, source_type: str | None = None) -> list[dict[str, Any]]:
        """
        Get all active data sources across all users.

        Useful for the sync Lambda to iterate over all sources.

        Args:
            source_type: Filter by source type (e.g., 'smashrun')

        Returns:
            List of user_source records with user info
        """
        query = self.supabase.table("user_sources").select("*, users(*)").eq("is_active", True)

        if source_type:
            query = query.eq("source_type", source_type)

        result = query.execute()

        return cast(list[dict[str, Any]], result.data)

    def deactivate_source(self, source_id: UUID) -> None:
        """
        Deactivate a data source (soft delete).

        Args:
            source_id: Source UUID
        """
        self.supabase.table("user_sources").update({"is_active": False}).eq(
            "id", str(source_id)
        ).execute()

        logger.info(f"Deactivated source {source_id}")
