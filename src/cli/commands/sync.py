"""Sync commands for stk CLI."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from cli import display

console = Console()

# Config directory
CONFIG_DIR = Path.home() / ".config" / "stk"
TOKENS_FILE = CONFIG_DIR / "tokens.json"
CONFIG_FILE = CONFIG_DIR / "config.json"
SYNC_STATE_FILE = CONFIG_DIR / "sync_state.json"


def ensure_config_dir() -> None:
    """Create config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def get_tokens() -> dict[str, Any] | None:
    """Load tokens from config file."""
    if not TOKENS_FILE.exists():
        return None
    with open(TOKENS_FILE) as f:
        data: dict[str, Any] = json.load(f)
        return data


def get_config() -> dict[str, Any]:
    """Load config from file."""
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE) as f:
        data: dict[str, Any] = json.load(f)
        return data


def save_tokens(token_data: dict[str, Any]) -> None:
    """Save tokens to config file."""
    ensure_config_dir()
    with open(TOKENS_FILE, "w") as f:
        json.dump(token_data, f, indent=2)


def get_last_sync_date() -> date:
    """Get last sync date from state file."""
    if not SYNC_STATE_FILE.exists():
        return date.today() - timedelta(days=30)

    with open(SYNC_STATE_FILE) as f:
        state = json.load(f)
        return date.fromisoformat(
            state.get("last_sync_date", str(date.today() - timedelta(days=30)))
        )


def update_sync_state(sync_date: date, runs_synced: int) -> None:
    """Update sync state file."""
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
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Fetch but don't store"),
) -> None:
    """
    Sync runs from SmashRun to MyRunStreak.

    Examples:
        stk sync                    # Sync recent runs
        stk sync --year 2015        # Sync all runs from 2015
        stk sync --since 2020-01-01 # Sync from Jan 1, 2020
        stk sync --full             # Sync everything (4000+ runs!)
    """
    # Check for tokens
    tokens = get_tokens()
    if not tokens:
        display.display_error("Not logged in. Run 'stk auth login' first.")
        raise typer.Exit(1)

    # Check for user_id
    config = get_config()
    user_id_str = config.get("user_id")
    if not user_id_str:
        display.display_error("No user ID. Run 'stk auth login' first.")
        raise typer.Exit(1)

    user_id = UUID(user_id_str)

    # Determine date range
    if year:
        since_date = date(year, 1, 1)
        until_date = date(year, 12, 31)
        display.display_info(f"Syncing year {year}")
    elif full:
        since_date = date(2010, 1, 1)  # SmashRun launch date
        until_date = date.today()
        display.display_info("Full sync - this may take a while for 4000+ runs")
    elif since:
        try:
            since_date = date.fromisoformat(since)
        except ValueError:
            display.display_error(f"Invalid date format: {since}. Use YYYY-MM-DD.")
            raise typer.Exit(1) from None
        until_date = date.fromisoformat(until) if until else date.today()
    else:
        since_date = get_last_sync_date()
        until_date = date.today()
        display.display_info(f"Syncing since {since_date}")

    # Import dependencies
    try:
        from shared.config import get_settings
        from shared.smashrun import SmashRunAPIClient, SmashRunOAuthClient
        from shared.supabase_client import get_supabase_client
        from shared.supabase_ops import RunsRepository, UsersRepository, activity_to_run_dict
    except ImportError as e:
        display.display_error(f"Missing dependencies: {e}")
        display.display_info("Run 'uv sync' to install dependencies")
        raise typer.Exit(1) from None

    # Get settings
    try:
        settings = get_settings()
    except Exception as e:
        display.display_error(f"Failed to load settings: {e}")
        display.display_info("Check your .env file")
        raise typer.Exit(1) from None

    # Check token expiration and refresh if needed
    oauth_client = SmashRunOAuthClient(
        client_id=settings.smashrun_client_id,
        client_secret=settings.smashrun_client_secret,
        redirect_uri=settings.smashrun_redirect_uri,
    )

    access_token = tokens.get("access_token")
    expires_at_str = tokens.get("expires_at")

    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if datetime.now(UTC) + timedelta(days=1) >= expires_at:
            display.display_sync_progress("Refreshing token...")
            try:
                new_tokens = oauth_client.refresh_access_token(tokens["refresh_token"])
                new_tokens["expires_at"] = (
                    datetime.now(UTC) + timedelta(seconds=new_tokens["expires_in"])
                ).isoformat()
                save_tokens(new_tokens)
                access_token = new_tokens["access_token"]
                display.display_sync_progress("Token refreshed", done=True)
            except Exception as e:
                display.display_error(f"Failed to refresh token: {e}")
                display.display_info("Try 'stk auth login' to re-authenticate")
                raise typer.Exit(1) from None

    # Sync runs
    runs_synced = 0
    runs_failed = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        fetch_task = progress.add_task("Connecting to SmashRun...", total=None)

        try:
            with SmashRunAPIClient(access_token=access_token) as api_client:
                # Get user info
                progress.update(fetch_task, description="Getting user info...")
                user_info = api_client.get_user_info()
                username = user_info.get("userName", "Unknown")

                # Fetch activities
                progress.update(
                    fetch_task,
                    description=f"Fetching runs {since_date} to {until_date}...",
                )

                # Use get_activities with date range for better control
                all_activities = []
                page = 0
                while True:
                    activities = api_client.get_activities(
                        page=page, count=100, since=since_date, until=until_date
                    )
                    if not activities:
                        break
                    all_activities.extend(activities)
                    progress.update(
                        fetch_task,
                        description=f"Fetched {len(all_activities)} runs...",
                    )
                    page += 1

                if not all_activities:
                    progress.update(fetch_task, description="No runs found", total=1, completed=1)
                    console.print()
                    display.display_info("No runs found in date range")
                    return

                progress.update(
                    fetch_task,
                    description=f"Found {len(all_activities)} runs",
                    total=1,
                    completed=1,
                )

                if dry_run:
                    console.print()
                    display.display_info(f"Dry run - would sync {len(all_activities)} runs")
                    return

                # Store to Supabase
                store_task = progress.add_task("Storing runs...", total=len(all_activities))

                supabase = get_supabase_client()
                runs_repo = RunsRepository(supabase)
                users_repo = UsersRepository(supabase)

                # Get source_id for this user
                sources = users_repo.get_user_sources(user_id)
                if not sources:
                    display.display_error("No SmashRun source found for user")
                    display.display_info("Try 'stk auth login' to re-register")
                    raise typer.Exit(1) from None

                source_id = UUID(sources[0]["id"])

                for activity_data in all_activities:
                    try:
                        # Parse activity
                        activity = api_client.parse_activity(activity_data)

                        # Convert to run dict
                        run_data = activity_to_run_dict(activity, user_id, source_id)

                        # Upsert to Supabase
                        runs_repo.upsert_run(user_id, source_id, run_data)

                        runs_synced += 1

                    except Exception as e:
                        runs_failed += 1
                        # Log but continue
                        console.print(f"[dim]Failed: {activity_data.get('activityId')}: {e}[/dim]")

                    progress.update(store_task, advance=1)

                progress.update(
                    store_task,
                    description=f"Stored {runs_synced} runs",
                )

        except Exception as e:
            display.display_error(f"Sync failed: {e}")
            raise typer.Exit(1) from None

    # Update sync state
    if runs_synced > 0:
        update_sync_state(until_date, runs_synced)

    # Show results
    console.print()
    if runs_failed > 0:
        display.display_warning(f"Synced {runs_synced} runs, {runs_failed} failed")
    else:
        display.display_sync_progress(f"Synced {runs_synced} runs as {username}", done=True)

    if runs_synced == 0:
        display.display_info("You're up to date!")
    else:
        display.display_info(f"Date range: {since_date} to {until_date}")
