"""K8s CronJob entry point: publish status.json to gs://myrunstreak-public.

Replaces the AWS Lambda that ran on EventBridge. Builds the same status
payload (matching the StreakData interface in the qualityplaybook.dev
RunningStreak.vue tile) and uploads it to GCS with a 5-minute Cache-Control.

Service-account JSON is read from the ``GCS_SERVICE_ACCOUNT_JSON`` env var
(materialized via ExternalSecrets from the ``myrunstreak-app-secrets`` AWS
Secret). The SA lives in GCP project ``missing-table`` and has
``roles/storage.objectAdmin`` on the bucket.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from google.cloud import storage
from google.oauth2 import service_account
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import GoalsRepository, RunsRepository, UsersRepository

GCS_BUCKET_NAME = "myrunstreak-public"
GCS_OBJECT_PATH = "status.json"
USER_TIMEZONE = ZoneInfo("America/New_York")
KM_TO_MILES = 0.621371

logger = logging.getLogger(__name__)


def km_to_miles(km: float) -> float:
    return km * KM_TO_MILES


def format_streak_duration(streak_start: str | None, today: date) -> str | None:
    """Render '11 years, 8 months and 9 days' from an ISO start date."""
    if not streak_start:
        return None

    start = date.fromisoformat(streak_start)
    delta = relativedelta(today, start)

    parts: list[str] = []
    if delta.years > 0:
        parts.append(f"{delta.years} year{'s' if delta.years != 1 else ''}")
    if delta.months > 0:
        parts.append(f"{delta.months} month{'s' if delta.months != 1 else ''}")
    if delta.days > 0 or not parts:
        parts.append(f"{delta.days} day{'s' if delta.days != 1 else ''}")

    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{parts[0]}, {parts[1]} and {parts[2]}"


def get_gcs_credentials() -> dict[str, Any]:
    """Parse GCS service-account JSON from the GCS_SERVICE_ACCOUNT_JSON env var."""
    raw = os.environ.get("GCS_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError(
            "GCS_SERVICE_ACCOUNT_JSON env var is empty or unset; "
            "expected the publisher SA JSON sourced from myrunstreak-secrets."
        )
    creds: dict[str, Any] = json.loads(raw)
    return creds


def upload_to_gcs(data: dict[str, Any]) -> str:
    """Upload ``data`` as JSON to gs://myrunstreak-public/status.json."""
    creds_dict = get_gcs_credentials()
    credentials = service_account.Credentials.from_service_account_info(creds_dict)  # type: ignore[no-untyped-call]
    client = storage.Client(credentials=credentials, project=creds_dict.get("project_id"))

    bucket = client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(GCS_OBJECT_PATH)
    blob.cache_control = "public, max-age=300"

    blob.upload_from_string(
        json.dumps(data, indent=2, default=str),
        content_type="application/json",
    )
    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{GCS_OBJECT_PATH}"
    logger.info(f"Uploaded status to {public_url}")
    return public_url


def build_goals_block(
    user_id: UUID,
    source_id: UUID | None,
    goals_repo: GoalsRepository,
    today: date,
) -> dict[str, Any]:
    """Yearly + monthly goal progress, in miles. Each is None when the user
    has no goal stored for the period (or no SmashRun source at all).

    Shape matches the GoalProgress interface in
    qualityplaybook.dev/frontend/src/components/RunningStreak.vue.
    """
    if source_id is None:
        return {"yearly": None, "monthly": None}

    def render(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if not row or row.get("goal_km") is None:
            return None
        goal_km = float(row["goal_km"])
        progress_km = float(row.get("progress_km") or 0.0)
        percent = (progress_km / goal_km * 100) if goal_km > 0 else None
        return {
            "goal_mi": round(km_to_miles(goal_km), 1),
            "progress_mi": round(km_to_miles(progress_km), 1),
            "percent": round(percent, 1) if percent is not None else None,
            "text": row.get("goal_text"),
            "fetched_at": row.get("fetched_at"),
        }

    yearly_row = goals_repo.get_by_period(user_id, source_id, today.year, None)
    monthly_row = goals_repo.get_by_period(user_id, source_id, today.year, today.month)
    return {"yearly": render(yearly_row), "monthly": render(monthly_row)}


def build_status_data(
    user_id: UUID,
    runs_repo: RunsRepository,
    goals_repo: GoalsRepository,
    source_id: UUID | None,
) -> dict[str, Any]:
    """Build the status.json payload — pre-aggregated stats with a
    recalculate fallback if the aggregation row is missing."""
    today = datetime.now(USER_TIMEZONE).date()
    seven_days_ago = today - timedelta(days=7)

    recent_runs = runs_repo.get_runs_by_date_range(user_id, seven_days_ago, today)
    ran_today = any(run["start_date"] == today.isoformat() for run in recent_runs)

    last_run: dict[str, Any] | None = None
    if recent_runs:
        latest = recent_runs[0]
        last_run = {
            "date": latest["start_date"],
            "distance_mi": round(km_to_miles(float(latest["distance_km"])), 2),
            "duration_min": round(float(latest["duration_seconds"]) / 60, 1),
        }

    last_7_days = [
        {
            "date": run["start_date"],
            "distance_mi": round(km_to_miles(float(run["distance_km"])), 2),
        }
        for run in recent_runs
    ]

    stats = runs_repo.get_user_running_stats(user_id)
    if not stats:
        logger.warning(f"No pre-calculated stats for user {user_id}, recalculating")
        try:
            stats = runs_repo.recalculate_user_stats(user_id, timezone="America/New_York")
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Failed to recalculate stats: {exc}; using defaults")
            stats = {}

    streak_days = stats.get("current_streak_days", 0)
    streak_start = stats.get("current_streak_start")
    streak_total_km = float(stats.get("current_streak_distance_km", 0))
    month_total_km = float(stats.get("month_to_date_distance_km", 0))
    year_total_km = float(stats.get("year_to_date_distance_km", 0))

    return {
        "updated_at": datetime.now(UTC).isoformat(),
        "ran_today": ran_today,
        "streak": {
            "current_days": streak_days,
            "started": streak_start,
            "duration": format_streak_duration(streak_start, today),
            "total_mi": round(km_to_miles(streak_total_km), 1),
        },
        "last_run": last_run,
        "last_7_days": last_7_days,
        "month_total_mi": round(km_to_miles(month_total_km), 1),
        "year_total_mi": round(km_to_miles(year_total_km), 1),
        "goals": build_goals_block(user_id, source_id, goals_repo, today),
    }


def resolve_user_and_source(users_repo: UsersRepository) -> tuple[UUID, UUID | None]:
    """Pick the user whose status to publish.

    Multi-user is out of scope today — there's exactly one active SmashRun
    source. When that grows we'll iterate, but for now the shape returned
    matches what the qualityplaybook.dev tile (and any future single-user
    embed) expects: a single status.json per known publisher.
    """
    sources = users_repo.get_all_active_sources(source_type="smashrun")
    if not sources:
        raise RuntimeError("No active SmashRun sources found")

    primary = sources[0]
    return UUID(primary["user_id"]), UUID(primary["id"])


def main() -> int:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=log_level)

    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)
    users_repo = UsersRepository(supabase)
    goals_repo = GoalsRepository(supabase)

    try:
        user_id, source_id = resolve_user_and_source(users_repo)
        logger.info(f"Publishing status for user {user_id}")

        status = build_status_data(user_id, runs_repo, goals_repo, source_id)
        upload_to_gcs(status)

        logger.info(
            f"Published: ran_today={status['ran_today']} "
            f"streak={status['streak']['current_days']}"
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error(f"publish_status failed: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
