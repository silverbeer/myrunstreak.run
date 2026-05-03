"""/sync-user — pulls runs from SmashRun for the authenticated user.

The standalone CronJob target lives in backend/jobs/sync_runs.py and shares the
same underlying ``run_user_sync`` helper.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends

from backend.auth import authenticate_request
from backend.cache import invalidate_user
from src.shared.secrets import get_smashrun_oauth_credentials
from src.shared.smashrun import SmashRunAPIClient, SmashRunOAuthClient
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import RunsRepository, TokenRepository, activity_to_run_dict

router = APIRouter(tags=["sync"])


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

    source_id = token_repo.get_source_id_for_user(user_id, "smashrun")
    if not source_id:
        raise ValueError(f"No SmashRun source found for user {user_id}")

    tokens = token_repo.get_user_tokens(user_id, "smashrun")
    if not tokens:
        raise ValueError(
            f"No tokens found for user {user_id}. Please authenticate first."
        )

    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    if token_repo.is_token_expired(user_id, "smashrun"):
        creds = get_smashrun_oauth_credentials()
        oauth = SmashRunOAuthClient(
            client_id=creds.get("client_id", ""),
            client_secret=creds.get("client_secret", ""),
            redirect_uri="urn:ietf:wg:oauth:2.0:oob",
        )
        new_tokens = oauth.refresh_access_token(refresh_token)
        access_token = new_tokens["access_token"]
        new_refresh = new_tokens.get("refresh_token", refresh_token)
        token_repo.save_user_tokens(
            user_id=user_id,
            access_token=access_token,
            refresh_token=new_refresh,
            expires_in=new_tokens.get("expires_in"),
            source_type="smashrun",
        )

    runs_synced = 0
    with SmashRunAPIClient(access_token=access_token) as api:
        activities = api.get_all_activities_since(since_date)
        activities = [
            a
            for a in activities
            if date.fromisoformat(a.get("startDateTimeLocal", "")[:10]) <= until_date
        ]
        for activity_data in activities:
            try:
                activity = api.parse_activity(activity_data)
                run_dict = activity_to_run_dict(activity, user_id, source_id)
                runs_repo.upsert_run(user_id, source_id, run_dict)
                runs_synced += 1
            except Exception:  # noqa: BLE001
                continue

    return {
        "message": "Sync completed",
        "runs_synced": runs_synced,
        "since": since_date.isoformat(),
        "until": until_date.isoformat(),
    }


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
