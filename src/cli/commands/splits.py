"""Splits commands for stk CLI — per-mile splits backfill (analysis: PR2)."""

from __future__ import annotations

from typing import Any

import typer

from cli import display
from cli.api import post_request

splits_app = typer.Typer(help="Per-mile splits — backfill from SmashRun.")


def backfill(
    since: str = typer.Option(None, "--since", "-s", help="Only runs on/after YYYY-MM-DD"),
    limit: int = typer.Option(50, "--limit", "-l", help="Runs per batch"),
    max_batches: int = typer.Option(200, "--max-batches", help="Safety cap on batches"),
) -> None:
    """Fetch + store per-mile splits for runs that don't have them yet.

    Runs in batches (the server rate-limits each one) until none remain.

        stk splits backfill --since 2026-01-01
    """
    body: dict[str, Any] = {"limit": limit}
    if since is not None:
        body["since"] = since

    total_runs = 0
    total_splits = 0
    display.display_sync_progress("Backfilling splits...")
    for _ in range(max_batches):
        result = post_request("sync-splits", data=body, timeout=180.0)
        processed = result.get("runs_processed", 0)
        synced = result.get("splits_synced", 0)
        remaining = result.get("remaining", 0)
        total_runs += processed
        total_splits += synced
        display.display_info(f"  {processed} runs, {synced} splits — {remaining} remaining")
        if remaining == 0 or processed == 0:
            break

    display.display_sync_progress(
        f"Backfilled {total_runs} runs ({total_splits} splits)", done=True
    )


splits_app.command(name="backfill")(backfill)
