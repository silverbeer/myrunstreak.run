#!/usr/bin/env python3
"""CLI client for querying MyRunStreak.com API endpoints.

Usage:
    python scripts/query_cli.py overall
    python scripts/query_cli.py recent --limit 5
    python scripts/query_cli.py monthly --limit 6
    python scripts/query_cli.py streaks
    python scripts/query_cli.py records
    python scripts/query_cli.py runs --offset 0 --limit 10

Environment variables:
    API_BASE_URL: Base URL for the API (default: dev endpoint)
"""

import argparse
import json
import os
import sys
from typing import Any

try:
    import httpx
except ImportError:
    print("❌ Error: 'httpx' library not installed")
    print("Install it with: uv sync")
    sys.exit(1)

# Try to import rich for pretty output, fall back to basic output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.json import JSON
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


DEFAULT_API_URL = "https://9fmuhcz4y0.execute-api.us-east-2.amazonaws.com/dev"

# Conversion factor
KM_TO_MILES = 0.621371


def km_to_miles(km: float) -> float:
    """Convert kilometers to miles."""
    return km * KM_TO_MILES


def get_api_url() -> str:
    """Get API base URL from environment or use default."""
    return os.getenv("API_BASE_URL", DEFAULT_API_URL)


def make_request(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make HTTP request to API endpoint."""
    url = f"{get_api_url()}/{endpoint}"

    try:
        response = httpx.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        print(f"❌ Request timed out after 30 seconds")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP error {e.response.status_code}: {e.response.text}")
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"❌ Request failed: {e}")
        sys.exit(1)


def print_json(data: dict[str, Any]) -> None:
    """Print JSON data with or without rich formatting."""
    if RICH_AVAILABLE:
        console = Console()
        console.print(JSON.from_data(data))
    else:
        print(json.dumps(data, indent=2))


def print_overall_stats(data: dict[str, Any]) -> None:
    """Print overall statistics."""
    total_miles = km_to_miles(data.get('total_km', 0))
    avg_miles = km_to_miles(data.get('avg_km', 0))
    longest_miles = km_to_miles(data.get('longest_run_km', 0))
    # Pace conversion: min/km to min/mile
    pace_min_per_mile = data.get('avg_pace_min_per_km', 0) / KM_TO_MILES

    if RICH_AVAILABLE:
        console = Console()

        table = Table(title="📊 Overall Running Statistics", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Runs", str(data.get("total_runs", 0)))
        table.add_row("Total Distance", f"{total_miles:.2f} miles")
        table.add_row("Average Distance", f"{avg_miles:.2f} miles")
        table.add_row("Longest Run", f"{longest_miles:.2f} miles")
        table.add_row("Average Pace", f"{pace_min_per_mile:.2f} min/mile")

        console.print(table)
    else:
        print("\n📊 Overall Running Statistics")
        print("=" * 50)
        print(f"Total Runs:       {data.get('total_runs', 0)}")
        print(f"Total Distance:   {total_miles:.2f} miles")
        print(f"Average Distance: {avg_miles:.2f} miles")
        print(f"Longest Run:      {longest_miles:.2f} miles")
        print(f"Average Pace:     {pace_min_per_mile:.2f} min/mile")


def print_recent_runs(data: dict[str, Any]) -> None:
    """Print recent runs."""
    runs = data.get("runs", [])

    if RICH_AVAILABLE:
        console = Console()

        table = Table(title=f"🏃 Recent Runs ({data.get('count', 0)} runs)", show_header=True)
        table.add_column("Date", style="cyan")
        table.add_column("Distance (mi)", justify="right", style="green")
        table.add_column("Duration", justify="right")
        table.add_column("Pace (min/mi)", justify="right", style="yellow")
        table.add_column("HR", justify="right", style="red")
        table.add_column("Temp (°F)", justify="right")

        for run in runs:
            distance_miles = km_to_miles(run.get('distance_km', 0))
            pace_min_per_mile = run.get('avg_pace_min_per_km', 0) / KM_TO_MILES
            temp_f = run.get('temperature_celsius', 0) * 9/5 + 32 if run.get('temperature_celsius') else None

            table.add_row(
                run.get("date", "")[:10],  # Just the date part
                f"{distance_miles:.2f}",
                f"{run.get('duration_minutes', 0):.1f} min",
                f"{pace_min_per_mile:.2f}",
                str(int(run.get("heart_rate_avg", 0))) if run.get("heart_rate_avg") else "-",
                str(int(temp_f)) if temp_f else "-",
            )

        console.print(table)
    else:
        print(f"\n🏃 Recent Runs ({data.get('count', 0)} runs)")
        print("=" * 80)
        for run in runs:
            distance_miles = km_to_miles(run.get('distance_km', 0))
            pace_min_per_mile = run.get('avg_pace_min_per_km', 0) / KM_TO_MILES
            print(f"{run.get('date', '')[:10]}: {distance_miles:.2f} mi, "
                  f"{run.get('duration_minutes', 0):.1f} min, "
                  f"{pace_min_per_mile:.2f} min/mi")


def print_monthly_stats(data: dict[str, Any]) -> None:
    """Print monthly statistics."""
    months = data.get("months", [])

    if RICH_AVAILABLE:
        console = Console()

        table = Table(title=f"📅 Monthly Statistics ({data.get('count', 0)} months)", show_header=True)
        table.add_column("Month", style="cyan")
        table.add_column("Runs", justify="right", style="green")
        table.add_column("Total (mi)", justify="right")
        table.add_column("Avg (mi)", justify="right")
        table.add_column("Avg Pace", justify="right", style="yellow")

        for month in months:
            total_miles = km_to_miles(month.get('total_km', 0))
            avg_miles = km_to_miles(month.get('avg_km', 0))
            pace_min_per_mile = month.get('avg_pace_min_per_km', 0) / KM_TO_MILES

            table.add_row(
                month.get("month", "")[:7],  # YYYY-MM
                str(month.get("run_count", 0)),
                f"{total_miles:.2f}",
                f"{avg_miles:.2f}",
                f"{pace_min_per_mile:.2f}",
            )

        console.print(table)
    else:
        print(f"\n📅 Monthly Statistics ({data.get('count', 0)} months)")
        print("=" * 80)
        for month in months:
            total_miles = km_to_miles(month.get('total_km', 0))
            avg_miles = km_to_miles(month.get('avg_km', 0))
            print(f"{month.get('month', '')[:7]}: {month.get('run_count', 0)} runs, "
                  f"{total_miles:.2f} mi total, "
                  f"{avg_miles:.2f} mi avg")


def print_streaks(data: dict[str, Any]) -> None:
    """Print running streaks."""
    if RICH_AVAILABLE:
        console = Console()

        # Current streak
        console.print(Panel(
            f"🔥 Current Streak: [bold green]{data.get('current_streak', 0)} days[/bold green]\n"
            f"🏆 Longest Streak: [bold yellow]{data.get('longest_streak', 0)} days[/bold yellow]",
            title="Running Streaks",
            border_style="cyan"
        ))

        # Top streaks table
        table = Table(title="🎯 Top Streaks", show_header=True)
        table.add_column("Start", style="cyan")
        table.add_column("End", style="cyan")
        table.add_column("Length (days)", justify="right", style="green")
        table.add_column("Current?", justify="center")

        for streak in data.get("top_streaks", []):
            is_current = "✓" if streak.get("is_current") else ""
            table.add_row(
                streak.get("start_date", ""),
                streak.get("end_date", ""),
                str(streak.get("length_days", 0)),
                is_current,
            )

        console.print(table)
    else:
        print("\n🔥 Running Streaks")
        print("=" * 50)
        print(f"Current Streak: {data.get('current_streak', 0)} days")
        print(f"Longest Streak: {data.get('longest_streak', 0)} days")
        print("\nTop Streaks:")
        for streak in data.get("top_streaks", []):
            current = " (CURRENT)" if streak.get("is_current") else ""
            print(f"  {streak.get('start_date', '')} to {streak.get('end_date', '')}: "
                  f"{streak.get('length_days', 0)} days{current}")


def print_records(data: dict[str, Any]) -> None:
    """Print personal records."""
    if RICH_AVAILABLE:
        console = Console()

        table = Table(title="🏆 Personal Records", show_header=True)
        table.add_column("Record", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Date", style="yellow")

        if "longest_run" in data:
            lr = data["longest_run"]
            distance_miles = km_to_miles(lr.get('distance_km', 0))
            table.add_row(
                "Longest Run",
                f"{distance_miles:.2f} miles",
                lr.get("date", "")
            )

        if "fastest_pace" in data:
            fp = data["fastest_pace"]
            pace_min_per_mile = fp.get('pace_min_per_km', 0) / KM_TO_MILES
            distance_miles = km_to_miles(fp.get('distance_km', 0))
            table.add_row(
                "Fastest Pace (3+ mi)",
                f"{pace_min_per_mile:.2f} min/mi ({distance_miles:.2f} mi)",
                fp.get("date", "")
            )

        if "most_km_week" in data:
            wk = data["most_km_week"]
            total_miles = km_to_miles(wk.get('total_km', 0))
            table.add_row(
                "Most Distance (Week)",
                f"{total_miles:.2f} miles",
                f"Week of {wk.get('week_start', '')}"
            )

        if "most_km_month" in data:
            mo = data["most_km_month"]
            total_miles = km_to_miles(mo.get('total_km', 0))
            table.add_row(
                "Most Distance (Month)",
                f"{total_miles:.2f} miles ({mo.get('run_count', 0)} runs)",
                mo.get("month", "")[:7]
            )

        console.print(table)
    else:
        print("\n🏆 Personal Records")
        print("=" * 50)
        if "longest_run" in data:
            lr = data["longest_run"]
            distance_miles = km_to_miles(lr.get('distance_km', 0))
            print(f"Longest Run: {distance_miles:.2f} miles on {lr.get('date', '')}")
        if "fastest_pace" in data:
            fp = data["fastest_pace"]
            pace_min_per_mile = fp.get('pace_min_per_km', 0) / KM_TO_MILES
            print(f"Fastest Pace: {pace_min_per_mile:.2f} min/mi on {fp.get('date', '')}")
        if "most_km_week" in data:
            wk = data["most_km_week"]
            total_miles = km_to_miles(wk.get('total_km', 0))
            print(f"Most Distance (Week): {total_miles:.2f} miles")
        if "most_km_month" in data:
            mo = data["most_km_month"]
            total_miles = km_to_miles(mo.get('total_km', 0))
            print(f"Most Distance (Month): {total_miles:.2f} miles ({mo.get('run_count', 0)} runs)")


def cmd_overall(args: argparse.Namespace) -> None:
    """Query overall statistics."""
    data = make_request("stats/overall")
    if args.json:
        print_json(data)
    else:
        print_overall_stats(data)


def cmd_recent(args: argparse.Namespace) -> None:
    """Query recent runs."""
    params = {"limit": args.limit}
    data = make_request("runs/recent", params)
    if args.json:
        print_json(data)
    else:
        print_recent_runs(data)


def cmd_monthly(args: argparse.Namespace) -> None:
    """Query monthly statistics."""
    params = {"limit": args.limit}
    data = make_request("stats/monthly", params)
    if args.json:
        print_json(data)
    else:
        print_monthly_stats(data)


def cmd_streaks(args: argparse.Namespace) -> None:
    """Query running streaks."""
    data = make_request("stats/streaks")
    if args.json:
        print_json(data)
    else:
        print_streaks(data)


def cmd_records(args: argparse.Namespace) -> None:
    """Query personal records."""
    data = make_request("stats/records")
    if args.json:
        print_json(data)
    else:
        print_records(data)


def cmd_runs(args: argparse.Namespace) -> None:
    """Query runs with pagination."""
    params = {"offset": args.offset, "limit": args.limit}
    data = make_request("runs", params)
    if args.json:
        print_json(data)
    else:
        print(f"\nShowing runs {args.offset + 1} to {args.offset + data.get('count', 0)} "
              f"of {data.get('total', 0)} total")
        print_recent_runs(data)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="CLI client for MyRunStreak.com API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/query_cli.py overall
  python scripts/query_cli.py recent --limit 5
  python scripts/query_cli.py monthly --limit 12
  python scripts/query_cli.py streaks
  python scripts/query_cli.py records
  python scripts/query_cli.py runs --offset 0 --limit 10

Environment:
  API_BASE_URL  Override API endpoint (default: dev)
        """
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted tables"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Overall stats
    subparsers.add_parser("overall", help="Get overall running statistics")

    # Recent runs
    recent_parser = subparsers.add_parser("recent", help="Get recent runs")
    recent_parser.add_argument("--limit", type=int, default=10, help="Number of runs (default: 10, max: 100)")

    # Monthly stats
    monthly_parser = subparsers.add_parser("monthly", help="Get monthly statistics")
    monthly_parser.add_argument("--limit", type=int, default=12, help="Number of months (default: 12, max: 60)")

    # Streaks
    subparsers.add_parser("streaks", help="Get running streak analysis")

    # Records
    subparsers.add_parser("records", help="Get personal records")

    # List runs
    runs_parser = subparsers.add_parser("runs", help="List all runs with pagination")
    runs_parser.add_argument("--offset", type=int, default=0, help="Offset for pagination (default: 0)")
    runs_parser.add_argument("--limit", type=int, default=50, help="Number of runs per page (default: 50, max: 100)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Show warning if rich is not available
    if not RICH_AVAILABLE and not args.json:
        print("💡 Tip: Install 'rich' for prettier output: uv pip install rich\n")

    # Route to appropriate command handler
    commands = {
        "overall": cmd_overall,
        "recent": cmd_recent,
        "monthly": cmd_monthly,
        "streaks": cmd_streaks,
        "records": cmd_records,
        "runs": cmd_runs,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
