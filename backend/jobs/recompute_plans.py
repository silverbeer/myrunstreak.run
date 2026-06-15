"""K8s CronJob entry point: nightly recompute of every active user's plan.

Re-aggregates each user's actuals and re-runs the planning engine for the
current month (and the next month once it's within reach), persisting fresh
``plan_days`` so the morning plan reflects yesterday's runs and any drift. The
plan is a derived cache; this job just advances ``today`` and rebuilds.

Mirrors the publish_status job's shape. Single-user today (one active SmashRun
source); the loop is ready for more.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from backend.planning import build_and_store_plan, period_for
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import UsersRepository

USER_TIMEZONE = ZoneInfo("America/New_York")

logger = logging.getLogger(__name__)


def resolve_user_ids(users_repo: UsersRepository) -> list[UUID]:
    """Active users whose plans to recompute. One SmashRun source today."""
    sources = users_repo.get_all_active_sources(source_type="smashrun")
    seen: dict[str, UUID] = {}
    for src in sources:
        seen.setdefault(src["user_id"], UUID(src["user_id"]))
    return list(seen.values())


def main() -> int:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=log_level)

    supabase = get_supabase_client()
    users_repo = UsersRepository(supabase)

    today = datetime.now(USER_TIMEZONE).date()
    period = period_for(today)

    try:
        user_ids = resolve_user_ids(users_repo)
        if not user_ids:
            logger.warning("No active users found; nothing to recompute")
            return 0

        failures = 0
        for user_id in user_ids:
            try:
                result = build_and_store_plan(supabase, user_id, period, today)
                logger.info(
                    f"Recomputed plan for user {user_id} {period}: "
                    f"{len(result.days)} prescriptions, status={result.status.value}"
                )
            except Exception as exc:  # noqa: BLE001 — one user must not sink the batch
                failures += 1
                logger.error(f"Recompute failed for user {user_id}: {exc}", exc_info=True)

        return 1 if failures else 0
    except Exception as exc:  # noqa: BLE001
        logger.error(f"recompute_plans failed: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
