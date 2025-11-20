"""SmashRun API client for fetching running activities."""

import logging
from datetime import date
from typing import Any, cast

import httpx

from ..models import Activity, Split

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
        incremental: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Fetch activities with pagination and optional date filtering.

        Args:
            page: Page number (0-indexed)
            count: Number of activities per page (max 100)
            since: Only fetch activities on or after this date
            until: Only fetch activities on or before this date
            incremental: If True, use fromDate to filter by sync date (for incremental syncs).
                        If False, filter by activity date client-side (for historical syncs).

        Returns:
            List of activity dictionaries from SmashRun API

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        params: dict[str, Any] = {
            "page": page,
            "count": min(count, 100),  # SmashRun max is 100
        }

        # SmashRun API 'fromDate' filters by SYNC date (when activity was added/updated),
        # not by activity date. Only use it for incremental syncs.
        if since and incremental:
            from datetime import datetime, timezone
            # Convert date to Unix timestamp (start of day UTC)
            since_dt = datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc)
            params["fromDate"] = int(since_dt.timestamp())

        logger.info(f"Fetching activities page {page} with count {count}")

        response = self.client.get("/my/activities/search", params=params)
        response.raise_for_status()

        activities = cast(list[dict[str, Any]], response.json())
        logger.info(f"Retrieved {len(activities)} activities from API")

        # Filter by activity date client-side (both since and until)
        if (since or until) and activities:
            from datetime import datetime

            filtered = []
            for activity in activities:
                # Parse startDateTimeLocal (format: "2025-11-20T06:30:00")
                start_str = activity.get("startDateTimeLocal", "")
                if start_str:
                    try:
                        activity_date = datetime.fromisoformat(start_str).date()
                        # Check since filter
                        if since and activity_date < since:
                            continue
                        # Check until filter
                        if until and activity_date > until:
                            continue
                        filtered.append(activity)
                    except ValueError:
                        # If we can't parse, include it
                        filtered.append(activity)
                else:
                    filtered.append(activity)

            logger.info(f"Filtered to {len(filtered)} activities ({since} to {until})")
            return filtered

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

        activity = cast(dict[str, Any], response.json())
        logger.info(f"Retrieved activity {activity_id}")

        return activity

    def get_activity_splits(self, activity_id: str, unit: str = "mi") -> list[dict[str, Any]]:
        """
        Fetch per-mile or per-kilometer splits for an activity.

        Args:
            activity_id: SmashRun activity ID
            unit: Either 'mi' for miles or 'km' for kilometers

        Returns:
            List of split dictionaries with speed and heart rate data

        Raises:
            httpx.HTTPStatusError: If activity not found or request fails
        """
        if unit not in ("mi", "km"):
            raise ValueError("unit must be 'mi' or 'km'")

        logger.info(f"Fetching {unit} splits for activity {activity_id}")

        response = self.client.get(f"/my/activities/{activity_id}/splits/{unit}")
        response.raise_for_status()

        splits = cast(list[dict[str, Any]], response.json())
        logger.info(f"Retrieved {len(splits)} splits for activity {activity_id}")

        return splits

    def get_all_activities_since(self, since: date, batch_size: int = 100) -> list[dict[str, Any]]:
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
            activities = self.get_activities(page=page, count=batch_size, since=since)

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

    def parse_splits(self, splits_data: list[dict[str, Any]]) -> list[Split]:
        """
        Parse SmashRun splits data into Split models.

        Args:
            splits_data: Raw splits list from SmashRun API

        Returns:
            List of validated Split models

        Raises:
            ValidationError: If splits data is invalid
        """
        return [Split(**split) for split in splits_data]

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

        user_info = cast(dict[str, Any], response.json())
        logger.info(f"Retrieved user info for: {user_info.get('userName')}")

        return user_info
