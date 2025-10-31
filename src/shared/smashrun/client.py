"""SmashRun API client for fetching running activities."""

import logging
from datetime import date, datetime
from typing import Any

import httpx

from ..models import Activity

logger = logging.getLogger(__name__)


class SmashRunAPIClient:
    """
    Client for interacting with SmashRun API.

    Handles authentication, request retries, rate limiting, and data fetching.
    """

    BASE_URL = "https://api.smashrun.com/v1"
    RATE_LIMIT = 250  # requests per hour

    def __init__(self, access_token: str) -> None:
        """
        Initialize API client with access token.

        Args:
            access_token: Valid SmashRun OAuth access token
        """
        self.access_token = access_token
        self._client: httpx.Client | None = None

    def __enter__(self) -> "SmashRunAPIClient":
        """Context manager entry."""
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            },
            timeout=30.0,
        )
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        if self._client:
            self._client.close()
            self._client = None

    @property
    def client(self) -> httpx.Client:
        """Get HTTP client, raising error if not in context manager."""
        if self._client is None:
            raise RuntimeError(
                "SmashRunAPIClient must be used as a context manager "
                "(use 'with SmashRunAPIClient(...) as client:')"
            )
        return self._client

    def get_activities(
        self,
        page: int = 0,
        count: int = 100,
        since: date | None = None,
        until: date | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch activities with pagination and optional date filtering.

        Args:
            page: Page number (0-indexed)
            count: Number of activities per page (max 100)
            since: Only fetch activities on or after this date
            until: Only fetch activities on or before this date

        Returns:
            List of activity dictionaries from SmashRun API

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        params: dict[str, Any] = {
            "page": page,
            "count": min(count, 100),  # SmashRun max is 100
        }

        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()

        logger.info(f"Fetching activities page {page} with count {count}")

        response = self.client.get("/my/activities/search", params=params)
        response.raise_for_status()

        activities = response.json()
        logger.info(f"Retrieved {len(activities)} activities")

        return activities

    def get_activity_by_id(self, activity_id: str) -> dict[str, Any]:
        """
        Fetch a specific activity by ID.

        Args:
            activity_id: SmashRun activity ID

        Returns:
            Activity dictionary from SmashRun API

        Raises:
            httpx.HTTPStatusError: If activity not found or request fails
        """
        logger.info(f"Fetching activity {activity_id}")

        response = self.client.get(f"/my/activities/{activity_id}")
        response.raise_for_status()

        activity = response.json()
        logger.info(f"Retrieved activity {activity_id}")

        return activity

    def get_all_activities_since(
        self, since: date, batch_size: int = 100
    ) -> list[dict[str, Any]]:
        """
        Fetch all activities since a given date (handles pagination automatically).

        Args:
            since: Fetch activities on or after this date
            batch_size: Number of activities to fetch per request

        Returns:
            List of all activity dictionaries since the given date

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        logger.info(f"Fetching all activities since {since}")

        all_activities: list[dict[str, Any]] = []
        page = 0

        while True:
            activities = self.get_activities(
                page=page, count=batch_size, since=since
            )

            if not activities:
                break

            all_activities.extend(activities)
            page += 1

            # If we got fewer than requested, we've reached the end
            if len(activities) < batch_size:
                break

        logger.info(f"Retrieved total of {len(all_activities)} activities")
        return all_activities

    def get_latest_activity(self) -> dict[str, Any] | None:
        """
        Fetch the most recent activity.

        Returns:
            Latest activity dictionary, or None if no activities exist

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        logger.info("Fetching latest activity")

        activities = self.get_activities(page=0, count=1)

        if not activities:
            logger.info("No activities found")
            return None

        logger.info(f"Retrieved latest activity: {activities[0].get('activityId')}")
        return activities[0]

    def parse_activity(self, activity_data: dict[str, Any]) -> Activity:
        """
        Parse SmashRun activity data into Activity model.

        Args:
            activity_data: Raw activity dictionary from SmashRun API

        Returns:
            Validated Activity model

        Raises:
            ValidationError: If activity data is invalid
        """
        return Activity(**activity_data)

    def get_user_info(self) -> dict[str, Any]:
        """
        Fetch authenticated user's profile information.

        Returns:
            User profile dictionary

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        logger.info("Fetching user info")

        response = self.client.get("/my/userinfo")
        response.raise_for_status()

        user_info = response.json()
        logger.info(f"Retrieved user info for: {user_info.get('userName')}")

        return user_info
