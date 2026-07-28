"""K8s CronJob entry point: trickle-backfill GPS polylines (SB-310).

Store-on-read (the /track endpoint) already stores a run's polyline whenever its
map is viewed. This job fills the long tail of never-viewed runs a gentle batch
at a time — one bounded, rate-limited pass per user per firing — so the territory
heatmap grows toward full history without ever flooding SmashRun (250 req/hr).

Resumable by construction: each run picks up the oldest runs that still lack a
polyline, so re-running (daily) advances until nothing remains.

Batch size is BACKFILL_TRACKS_BATCH_LIMIT (default 100). The CronJob fires
several times a day, so the daily total is that limit times the schedule.
"""

from __future__ import annotations

import logging
import os
import sys
from uuid import UUID

from backend.config import get_settings
from backend.routes.sync import backfill_user_tracks
from src.shared.supabase_client import get_supabase_client


def main() -> int:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger = logging.getLogger("backfill-tracks-cron")

    # DAILY_LIMIT is the old name — still honoured so a chart/image rollout in
    # either order keeps the configured batch size.
    batch_limit = int(
        os.environ.get("BACKFILL_TRACKS_BATCH_LIMIT")
        or os.environ.get("BACKFILL_TRACKS_DAILY_LIMIT")
        or "100"
    )

    supabase = get_supabase_client()
    rows = supabase.table("user_sources").select("user_id").eq("source_type", "smashrun").execute()
    user_ids: list[UUID] = [UUID(r["user_id"]) for r in (rows.data or [])]

    if not user_ids:
        logger.info("No users with SmashRun sources to backfill")
        return 0

    failures = 0
    for user_id in user_ids:
        try:
            result = backfill_user_tracks(user_id, limit=batch_limit)
            logger.info(
                "Backfilled %s tracks for %s (%s processed, %s remaining)",
                result["tracks_stored"],
                user_id,
                result["runs_processed"],
                result["remaining"],
            )
        except Exception as exc:  # noqa: BLE001
            failures += 1
            logger.error(f"Track backfill failed for {user_id}: {exc}", exc_info=True)

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
