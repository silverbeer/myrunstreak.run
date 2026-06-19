"""/sync-user — pulls runs from SmashRun for the authenticated user.

The standalone CronJob target lives in backend/jobs/sync_runs.py and shares the
same underlying ``run_user_sync`` helper.
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from backend.auth import authenticate_request
from backend.cache import invalidate_user
from backend.config import Settings, get_settings
from fastapi import APIRouter, Body, Depends
from src.shared.secrets import get_smashrun_oauth_credentials
from src.shared.smashrun import SmashRunAPIClient, SmashRunOAuthClient
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import (
    GoalsRepository,
    RunsRepository,
    TokenRepository,
    activity_to_run_dict,
    split_to_dict,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sync"])

# Forward-fill splits inline only for modest sync windows; a full/historical
# sync would fire thousands of per-activity split calls, so those defer to the
# dedicated batched backfill (/sync-splits).
SPLITS_INLINE_MAX = 50
SPLITS_UNIT = "mi"  # mile-boundary splits — "1st mile / 2nd mile" analysis


def store_run_splits(
    api: SmashRunAPIClient,
    runs_repo: RunsRepository,
    run_id: UUID,
    activity_id: str,
    unit: str = SPLITS_UNIT,
) -> int:
    """Fetch one activity's splits from SmashRun and store them; mark the run.

    Returns the number of splits stored. Idempotent (upsert on
    run_id,split_unit,split_number).
    """
    raw = api.get_activity_splits(activity_id, unit=unit)
    splits = api.parse_splits(raw)
    for i, split in enumerate(splits, start=1):
        runs_repo.upsert_split(run_id, split_to_dict(split, run_id, split_number=i, unit=unit))
    runs_repo.set_has_splits(run_id, True)
    return len(splits)


def _resolve_access_token(user_id: UUID, token_repo: TokenRepository) -> str:
    """Current SmashRun access token for the user, refreshing if expired."""
    tokens = token_repo.get_user_tokens(user_id, "smashrun")
    if not tokens:
        raise ValueError(f"No tokens found for user {user_id}. Please authenticate first.")

    access_token = tokens["access_token"]
    if token_repo.is_token_expired(user_id, "smashrun"):
        creds = get_smashrun_oauth_credentials()
        oauth = SmashRunOAuthClient(
            client_id=creds.get("client_id", ""),
            client_secret=creds.get("client_secret", ""),
            redirect_uri="urn:ietf:wg:oauth:2.0:oob",
        )
        new_tokens = oauth.refresh_access_token(tokens["refresh_token"])
        access_token = new_tokens["access_token"]
        token_repo.save_user_tokens(
            user_id=user_id,
            access_token=access_token,
            refresh_token=new_tokens.get("refresh_token", tokens["refresh_token"]),
            expires_in=new_tokens.get("expires_in"),
            source_type="smashrun",
        )
    return str(access_token)


def run_user_sync(
    user_id: UUID,
    since: date | None = None,
    until: date | None = None,
    full: bool = False,
) -> dict[str, Any]:
    """Synchronous core sync routine — invoked by both the HTTP endpoint and
    the K8s CronJob entry point in ``backend/jobs/sync_runs.py``.
    """
    if full:
        since_date = date(2010, 1, 1)
        until_date = date.today()
    else:
        since_date = since or (date.today() - timedelta(days=7))
        until_date = until or date.today()

    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)
    token_repo = TokenRepository(supabase)
    goals_repo = GoalsRepository(supabase)
    settings = get_settings()

    source_id = token_repo.get_source_id_for_user(user_id, "smashrun")
    if not source_id:
        raise ValueError(f"No SmashRun source found for user {user_id}")

    access_token = _resolve_access_token(user_id, token_repo)

    runs_synced = 0
    splits_synced = 0
    with SmashRunAPIClient(access_token=access_token) as api:
        activities = api.get_all_activities_since(since_date)
        activities = [
            a
            for a in activities
            if date.fromisoformat(a.get("startDateTimeLocal", "")[:10]) <= until_date
        ]
        synced: list[tuple[str, str]] = []  # (run_id, source_activity_id)
        for activity_data in activities:
            try:
                activity = api.parse_activity(activity_data)
                run_dict = activity_to_run_dict(activity, user_id, source_id)
                run = runs_repo.upsert_run(user_id, source_id, run_dict)
                runs_synced += 1
                synced.append((run["id"], activity.activity_id))
            except Exception:  # noqa: BLE001
                continue

        # Forward-fill splits for this batch (best-effort, never fail the sync).
        # Skipped on full/large windows — those use the batched backfill instead.
        if not full and len(synced) <= SPLITS_INLINE_MAX:
            for run_id, activity_id in synced:
                try:
                    splits_synced += store_run_splits(api, runs_repo, UUID(run_id), activity_id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"Split sync failed for activity {activity_id}: {exc}")

        # Refresh yearly + monthly goals for the current period if stale or
        # missing. Failure here must not fail the whole sync.
        try:
            sync_current_goals(
                user_id=user_id,
                source_id=source_id,
                api=api,
                goals_repo=goals_repo,
                settings=settings,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Goal sync failed for source {source_id}: {exc}")

    # Refresh user_running_stats so streak/totals reflect the runs we just
    # upserted. The aggregation row is what status.json + the dashboard
    # both read; without this call it stays frozen at the prior sync's
    # values (e.g. last_run_date never advances past the old streak end).
    try:
        runs_repo.recalculate_user_stats(user_id, timezone="America/New_York")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"recalculate_user_stats failed for {user_id}: {exc}")

    return {
        "message": "Sync completed",
        "runs_synced": runs_synced,
        "splits_synced": splits_synced,
        "since": since_date.isoformat(),
        "until": until_date.isoformat(),
    }


def backfill_user_splits(
    user_id: UUID,
    since: date | None = None,
    until: date | None = None,
    limit: int = 50,
    sleep_seconds: float = 0.4,
) -> dict[str, Any]:
    """Fetch + store splits for runs that don't have them yet (oldest gap first).

    Batched + rate-limited so it can be called repeatedly until ``remaining`` is
    0. Returns counts so a CLI can drive it in a loop.
    """
    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)
    token_repo = TokenRepository(supabase)

    pending = runs_repo.get_runs_missing_splits(user_id, since=since, until=until, limit=limit)
    if not pending:
        return {"runs_processed": 0, "splits_synced": 0, "remaining": 0}

    access_token = _resolve_access_token(user_id, token_repo)
    runs_processed = 0
    splits_synced = 0
    with SmashRunAPIClient(access_token=access_token) as api:
        for row in pending:
            activity_id = row.get("source_activity_id")
            if not activity_id:
                continue
            try:
                splits_synced += store_run_splits(api, runs_repo, UUID(row["id"]), activity_id)
                runs_processed += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Backfill split failed for activity {activity_id}: {exc}")
                runs_repo.set_has_splits(UUID(row["id"]), False)
            time.sleep(sleep_seconds)  # be gentle with the SmashRun API

    remaining = len(runs_repo.get_runs_missing_splits(user_id, since=since, until=until, limit=1))
    return {
        "runs_processed": runs_processed,
        "splits_synced": splits_synced,
        "remaining": remaining,  # >0 means call again to continue
    }


def sync_current_goals(
    user_id: UUID,
    source_id: UUID,
    api: SmashRunAPIClient,
    goals_repo: GoalsRepository,
    settings: Settings,
) -> None:
    """Refresh current-year and current-month goals from SmashRun if stale.

    Yearly and monthly periods have separate staleness thresholds
    (``settings.goal_yearly_staleness_days`` / ``goal_monthly_staleness_days``)
    so we don't re-fetch the same goal every sync. Periods with no goal set on
    SmashRun are recorded as "absent" via :meth:`GoalsRepository.mark_absent`
    so we don't keep hammering the API.
    """
    today = date.today()
    yearly_ttl = timedelta(days=settings.goal_yearly_staleness_days)
    monthly_ttl = timedelta(days=settings.goal_monthly_staleness_days)

    periods: list[tuple[int, int | None, timedelta]] = [
        (today.year, None, yearly_ttl),
        (today.year, today.month, monthly_ttl),
    ]

    for year, month, ttl in periods:
        label = f"{year}" if month is None else f"{year}/{month}"
        existing = goals_repo.get_by_period(user_id, source_id, year, month)

        if not goals_repo.is_stale(existing, ttl):
            logger.debug(f"Goal {label} is fresh, skipping fetch")
            continue

        logger.info(f"Fetching goal {label} from SmashRun")
        goal = api.get_goal(year, month)

        if goal is None:
            goals_repo.mark_absent(user_id, source_id, year, month)
            logger.info(f"No goal set on SmashRun for {label}")
        else:
            goals_repo.upsert(user_id, source_id, goal)
            logger.info(
                f"Stored goal {label}: goal_km={goal.goal_km} progress_km={goal.progress_km}"
            )


@router.post("/sync-user")
async def sync_user(
    user_id: UUID = Depends(authenticate_request),
    body: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    since = date.fromisoformat(body["since"]) if body.get("since") else None
    until = date.fromisoformat(body["until"]) if body.get("until") else None
    full = bool(body.get("full"))

    result = run_user_sync(user_id, since=since, until=until, full=full)
    await invalidate_user(user_id)
    return result


@router.post("/sync-splits")
async def sync_splits(
    user_id: UUID = Depends(authenticate_request),
    body: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    """Backfill per-mile splits for runs that don't have them, one batch per call.

    Body: {since?, until?, limit?}. Returns {runs_processed, splits_synced,
    remaining}; call repeatedly while ``remaining`` > 0.
    """
    since = date.fromisoformat(body["since"]) if body.get("since") else None
    until = date.fromisoformat(body["until"]) if body.get("until") else None
    limit = int(body.get("limit", 50))
    return backfill_user_splits(user_id, since=since, until=until, limit=limit)
