"""K8s CronJob entry point: sync runs for every enrolled user.

Mirrors what EventBridge → sync Lambda did before. Iterates users with a
SmashRun source token and runs the same ``run_user_sync`` helper used by
the HTTP endpoint.
"""

from __future__ import annotations

import logging
import sys
from uuid import UUID

from backend.config import get_settings
from backend.routes.sync import run_user_sync
from src.shared.supabase_client import get_supabase_client


def main() -> int:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger = logging.getLogger("sync-cron")

    supabase = get_supabase_client()
    rows = (
        supabase.table("user_sources")
        .select("user_id")
        .eq("source_type", "smashrun")
        .execute()
    )
    user_ids: list[UUID] = [UUID(r["user_id"]) for r in (rows.data or [])]

    if not user_ids:
        logger.info("No users with SmashRun sources to sync")
        return 0

    failures = 0
    for user_id in user_ids:
        try:
            result = run_user_sync(user_id)
            logger.info(f"Synced {result['runs_synced']} runs for {user_id}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            logger.error(f"Sync failed for {user_id}: {exc}", exc_info=True)

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
