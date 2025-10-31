#!/usr/bin/env python3
"""
Local testing script for Lambda sync function.

This script simulates the Lambda function locally without AWS dependencies.
Uses local file storage instead of Secrets Manager and local DuckDB.

Usage:
    python scripts/test_local_sync.py
"""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from src.shared.config import get_settings
from src.shared.duckdb_ops import DuckDBManager, RunRepository
from src.shared.smashrun import SmashRunAPIClient, SmashRunOAuthClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Local storage paths
DATA_DIR = Path("./data")
TOKENS_FILE = DATA_DIR / "smashrun_tokens.json"
SYNC_STATE_FILE = DATA_DIR / "sync_state.json"
DUCKDB_FILE = DATA_DIR / "runs.duckdb"


def ensure_data_dir():
    """Create data directory if it doesn't exist."""
    DATA_DIR.mkdir(exist_ok=True)
    logger.info(f"Using data directory: {DATA_DIR.absolute()}")


def run_oauth_flow(oauth_client: SmashRunOAuthClient) -> dict:
    """
    Run OAuth flow to get tokens.

    Returns:
        Token data dictionary
    """
    print("\n" + "=" * 60)
    print("Step 1: Authorize with SmashRun")
    print("=" * 60)

    auth_url = oauth_client.get_authorization_url(state="local_test")
    print(f"\nVisit this URL:\n{auth_url}\n")
    print("After authorizing, you'll be redirected to:")
    print("http://localhost:8000/callback?code=AUTH_CODE&state=local_test")

    auth_code = input("\nPaste the authorization code: ").strip()

    if not auth_code:
        raise ValueError("No authorization code provided")

    print("\nExchanging code for tokens...")
    token_data = oauth_client.exchange_code_for_token(auth_code)

    # Add expiration timestamp
    token_data["expires_at"] = (
        datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
    ).isoformat()

    print("✓ Successfully obtained tokens")
    return token_data


def save_tokens(token_data: dict):
    """Save tokens to local file."""
    with open(TOKENS_FILE, "w") as f:
        json.dump(token_data, f, indent=2)
    logger.info(f"Saved tokens to {TOKENS_FILE}")


def load_tokens() -> dict:
    """Load tokens from local file."""
    if not TOKENS_FILE.exists():
        raise FileNotFoundError(
            f"Tokens file not found: {TOKENS_FILE}\n"
            "Run OAuth flow first."
        )

    with open(TOKENS_FILE) as f:
        return json.load(f)


def get_valid_access_token(oauth_client: SmashRunOAuthClient) -> str:
    """
    Get valid access token, refreshing if needed.

    Returns:
        Valid access token
    """
    token_data = load_tokens()

    # Check if token needs refresh
    expires_at = datetime.fromisoformat(token_data["expires_at"])
    now = datetime.utcnow()

    if now + timedelta(days=1) >= expires_at:
        logger.info("Token expired or expiring soon, refreshing...")

        new_tokens = oauth_client.refresh_access_token(token_data["refresh_token"])
        new_tokens["expires_at"] = (
            datetime.utcnow() + timedelta(seconds=new_tokens["expires_in"])
        ).isoformat()

        save_tokens(new_tokens)
        logger.info("✓ Token refreshed")
        return new_tokens["access_token"]

    logger.info("Using existing access token")
    return token_data["access_token"]


def get_last_sync_date() -> date:
    """Get last sync date from local file."""
    if not SYNC_STATE_FILE.exists():
        # Default to 30 days ago
        default_date = date.today() - timedelta(days=30)
        logger.info(f"No sync state found, using default: {default_date}")
        return default_date

    with open(SYNC_STATE_FILE) as f:
        state = json.load(f)
        last_sync = date.fromisoformat(state["last_sync_date"])
        logger.info(f"Last sync date: {last_sync}")
        return last_sync


def update_sync_state(sync_date: date, runs_synced: int):
    """Update sync state in local file."""
    state = {
        "last_sync_date": sync_date.isoformat(),
        "last_sync_timestamp": datetime.utcnow().isoformat(),
        "runs_synced": runs_synced,
    }

    with open(SYNC_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    logger.info(f"Updated sync state: {runs_synced} runs synced")


def sync_runs(access_token: str, since_date: date) -> int:
    """
    Sync runs from SmashRun to local DuckDB.

    Returns:
        Number of runs synced
    """
    logger.info(f"Syncing runs since {since_date}")

    runs_synced = 0

    # Initialize database
    db_manager = DuckDBManager(str(DUCKDB_FILE))

    if not db_manager.table_exists("runs"):
        logger.info("Initializing database schema")
        db_manager.initialize_schema()

    # Fetch and store runs
    with SmashRunAPIClient(access_token=access_token) as api_client:
        # Get user info
        user_info = api_client.get_user_info()
        logger.info(f"Authenticated as: {user_info.get('userName')}")

        # Fetch activities
        logger.info(f"Fetching activities since {since_date}...")
        activities = api_client.get_all_activities_since(since_date)
        logger.info(f"Found {len(activities)} activities")

        if not activities:
            logger.info("No new activities to sync")
            return 0

        # Store in database
        with db_manager as conn:
            repo = RunRepository(conn)

            for activity_data in activities:
                try:
                    activity = api_client.parse_activity(activity_data)
                    repo.upsert_run(activity)

                    runs_synced += 1
                    logger.info(
                        f"✓ Synced: {activity.start_date_time_local.date()} - "
                        f"{activity.distance_miles:.2f} mi - "
                        f"Pace: {activity.average_pace_min_per_mile:.1f} min/mi"
                    )

                except Exception as e:
                    logger.error(f"Failed to process activity: {e}")
                    continue

    logger.info(f"Successfully synced {runs_synced} runs")
    return runs_synced


def show_stats():
    """Display statistics from local database."""
    db_manager = DuckDBManager(str(DUCKDB_FILE))

    if not db_manager.table_exists("runs"):
        logger.info("No data in database yet")
        return

    with db_manager as conn:
        repo = RunRepository(conn)

        print("\n" + "=" * 60)
        print("Running Statistics (in miles!)")
        print("=" * 60)

        # Total runs
        total_runs = repo.get_total_runs()
        print(f"\nTotal Runs: {total_runs}")

        if total_runs == 0:
            return

        # Current streak
        current_streak = repo.get_current_streak()
        print(f"Current Streak: {current_streak} days")

        # Latest run
        latest_run = repo.get_latest_run()
        if latest_run:
            print(f"\nLatest Run:")
            print(f"  Date: {latest_run['start_date']}")
            print(f"  Distance: {latest_run['distance_km'] * 0.621371:.2f} miles")
            print(f"  Duration: {latest_run['duration_seconds'] // 60} minutes")
            print(f"  Pace: {latest_run['average_pace_min_per_km'] / 0.621371:.1f} min/mi")

        # Query using miles view
        result = conn.execute("""
            SELECT
                COUNT(*) as total_runs,
                SUM(distance_miles) as total_miles,
                AVG(distance_miles) as avg_miles,
                AVG(average_pace_min_per_mile) as avg_pace
            FROM runs_miles
        """).fetchone()

        if result:
            print(f"\nOverall Statistics:")
            print(f"  Total Distance: {result[1]:.1f} miles")
            print(f"  Average Distance: {result[2]:.1f} miles per run")
            print(f"  Average Pace: {result[3]:.1f} min/mile")

        print()


def main():
    """Main local testing flow."""
    print("=" * 60)
    print("MyRunStreak.com - Local Lambda Testing")
    print("=" * 60)

    ensure_data_dir()

    # Load settings
    settings = get_settings()

    # Create OAuth client
    oauth_client = SmashRunOAuthClient(
        client_id=settings.smashrun_client_id,
        client_secret=settings.smashrun_client_secret,
        redirect_uri=settings.smashrun_redirect_uri,
    )

    # Check if we have tokens
    if not TOKENS_FILE.exists():
        print("\n📝 No tokens found. Running OAuth flow...")
        token_data = run_oauth_flow(oauth_client)
        save_tokens(token_data)
        print("\n✓ Tokens saved locally")
    else:
        print(f"\n✓ Using existing tokens from {TOKENS_FILE}")

    # Get valid access token
    print("\n" + "=" * 60)
    print("Step 2: Get Valid Access Token")
    print("=" * 60)
    access_token = get_valid_access_token(oauth_client)
    print("✓ Access token ready")

    # Get last sync date
    print("\n" + "=" * 60)
    print("Step 3: Check Last Sync Date")
    print("=" * 60)
    last_sync_date = get_last_sync_date()
    print(f"Will fetch runs since: {last_sync_date}")

    # Sync runs
    print("\n" + "=" * 60)
    print("Step 4: Sync Runs from SmashRun")
    print("=" * 60)
    runs_synced = sync_runs(access_token, last_sync_date)

    # Update sync state
    if runs_synced > 0:
        update_sync_state(date.today(), runs_synced)

    # Show stats
    show_stats()

    # Success!
    print("=" * 60)
    print("Local Test Complete!")
    print("=" * 60)
    print(f"\n✓ Synced {runs_synced} runs")
    print(f"✓ Data stored in: {DUCKDB_FILE.absolute()}")
    print(f"✓ Tokens stored in: {TOKENS_FILE.absolute()}")
    print(f"✓ Sync state in: {SYNC_STATE_FILE.absolute()}")

    print("\nYou can now:")
    print("  • Query the database with DuckDB CLI")
    print("  • View runs in miles using runs_miles view")
    print("  • Run this script again to sync new runs")
    print("  • Deploy to AWS Lambda when ready!")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
    except Exception as e:
        logger.exception(f"Test failed: {e}")
        print("\n❌ Test failed. Check logs above for details.")
