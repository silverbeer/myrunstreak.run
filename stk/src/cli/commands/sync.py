"""Sync commands for stk CLI."""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from cli import display
from cli.api import post_request

console = Console()

# Config directory
CONFIG_DIR = Path.home() / ".config" / "stk"
SYNC_STATE_FILE = CONFIG_DIR / "sync_state.json"


def ensure_config_dir() -> None:
    """Create config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def get_last_sync_date() -> date:
    """Get last sync date from state file."""
    if not SYNC_STATE_FILE.exists():
        return date.today() - timedelta(days=30)

    with open(SYNC_STATE_FILE) as f:
        state: dict[str, Any] = json.load(f)
        return date.fromisoformat(
            state.get("last_sync_date", str(date.today() - timedelta(days=30)))
        )


def update_sync_state(sync_date: date, runs_synced: int) -> None:
    """Update sync state file."""
    from datetime import UTC, datetime

    ensure_config_dir()
    state = {
        "last_sync_date": sync_date.isoformat(),
        "last_sync_timestamp": datetime.now(UTC).isoformat(),
        "runs_synced": runs_synced,
    }
    with open(SYNC_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def sync_runs(
    since: str | None = typer.Option(None, "--since", "-s", help="Sync from date (YYYY-MM-DD)"),
    until: str | None = typer.Option(None, "--until", "-u", help="Sync until date (YYYY-MM-DD)"),
    year: int | None = typer.Option(None, "--year", "-y", help="Sync a specific year"),
    full: bool = typer.Option(False, "--full", "-f", help="Full sync (all time)"),
) -> None:
    """
    Sync runs from SmashRun to MyRunStreak.

    Examples:
        stk sync                    # Sync recent runs
        stk sync --year 2015        # Sync all runs from 2015
        stk sync --since 2020-01-01 # Sync from Jan 1, 2020
        stk sync --full             # Sync everything (4000+ runs!)
    """
    # Determine date range
    if year:
        since_date = date(year, 1, 1)
        until_date = date(year, 12, 31)
        display.display_info(f"Syncing year {year}")
    elif full:
        since_date = date(2010, 1, 1)  # SmashRun launch date
        until_date = date.today()
        display.display_info("Full sync - this may take a while for 4000+ runs")
    elif since or until:
        # Parse since date
        if since:
            try:
                since_date = date.fromisoformat(since)
            except ValueError:
                display.display_error(f"Invalid date format: {since}. Use YYYY-MM-DD.")
                raise typer.Exit(1) from None
        else:
            since_date = get_last_sync_date()

        # Parse until date
        if until:
            try:
                until_date = date.fromisoformat(until)
            except ValueError:
                display.display_error(f"Invalid date format: {until}. Use YYYY-MM-DD.")
                raise typer.Exit(1) from None
        else:
            until_date = date.today()

        display.display_info(f"Syncing {since_date} to {until_date}")
    else:
        # Default: incremental sync from last sync date
        since_date = get_last_sync_date()
        until_date = date.today()
        display.display_info(f"Syncing since {since_date}")

    # Build request body
    request_data: dict[str, Any] = {}
    if full:
        request_data["full"] = True
    else:
        request_data["since"] = since_date.isoformat()
        request_data["until"] = until_date.isoformat()

    # Call API with longer timeout for sync operations
    display.display_sync_progress("Syncing runs...")

    try:
        # Use 120 second timeout for sync operations (may take a while for full sync)
        result = post_request("sync-user", data=request_data, timeout=120.0)

        runs_synced = result.get("runs_synced", 0)
        sync_since = result.get("since", since_date.isoformat())
        sync_until = result.get("until", until_date.isoformat())

        # Update local sync state
        if runs_synced > 0:
            update_sync_state(date.fromisoformat(sync_until), runs_synced)

        # Show results
        console.print()
        display.display_sync_progress(f"Synced {runs_synced} runs", done=True)

        if runs_synced == 0:
            display.display_info("You're up to date!")
        else:
            display.display_info(f"Date range: {sync_since} to {sync_until}")

    except SystemExit:
        # Re-raise SystemExit from post_request error handling
        raise
    except Exception as e:
        display.display_error(f"Sync failed: {e}")
        raise typer.Exit(1) from None
