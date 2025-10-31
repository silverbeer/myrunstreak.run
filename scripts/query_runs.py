#!/usr/bin/env python3
"""
Query local DuckDB database for running statistics.

Usage:
    python scripts/query_runs.py
"""

import logging
from pathlib import Path

from src.shared.duckdb_ops import DuckDBManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DUCKDB_FILE = Path("./data/runs.duckdb")


def print_table(title: str, rows: list, headers: list):
    """Print formatted table."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

    if not rows:
        print("No data")
        return

    # Print headers
    print()
    for header in headers:
        print(f"{header:20}", end="")
    print()
    print("-" * 80)

    # Print rows
    for row in rows:
        for value in row:
            if isinstance(value, float):
                print(f"{value:20.2f}", end="")
            else:
                print(f"{str(value):20}", end="")
        print()


def main():
    """Query and display running statistics."""
    if not DUCKDB_FILE.exists():
        print(f"Database not found: {DUCKDB_FILE}")
        print("Run 'python scripts/test_local_sync.py' first to sync your runs.")
        return

    db_manager = DuckDBManager(str(DUCKDB_FILE))

    with db_manager as conn:
        print("\n🏃 MyRunStreak.com - Running Statistics (in miles!)")

        # Overall stats
        result = conn.execute("""
            SELECT
                COUNT(*) as total_runs,
                SUM(distance_miles) as total_miles,
                AVG(distance_miles) as avg_miles,
                MAX(distance_miles) as longest_run,
                AVG(average_pace_min_per_mile) as avg_pace
            FROM runs_miles
        """).fetchone()

        if result and result[0] > 0:
            print("\n" + "=" * 80)
            print("Overall Statistics")
            print("=" * 80)
            print(f"\nTotal Runs:        {result[0]}")
            print(f"Total Distance:    {result[1]:.1f} miles")
            print(f"Average Distance:  {result[2]:.1f} miles per run")
            print(f"Longest Run:       {result[3]:.1f} miles")
            print(f"Average Pace:      {result[4]:.1f} min/mile")

        # Recent runs
        recent = conn.execute("""
            SELECT
                start_date,
                distance_miles,
                duration_seconds / 60.0 as duration_min,
                average_pace_min_per_mile,
                terrain,
                how_felt
            FROM runs_miles
            ORDER BY start_date DESC
            LIMIT 10
        """).fetchall()

        if recent:
            print_table(
                "Recent Runs (Last 10)",
                recent,
                ["Date", "Miles", "Duration (min)", "Pace (min/mi)", "Terrain", "Felt"]
            )

        # Monthly summary
        monthly = conn.execute("""
            SELECT
                start_year || '-' || LPAD(CAST(start_month AS VARCHAR), 2, '0') as month,
                run_count,
                total_distance_miles,
                avg_distance_miles,
                avg_pace_min_per_mile
            FROM monthly_summary_miles
            ORDER BY start_year DESC, start_month DESC
            LIMIT 12
        """).fetchall()

        if monthly:
            print_table(
                "Monthly Summary (Last 12 Months)",
                monthly,
                ["Month", "Runs", "Total Miles", "Avg Miles", "Avg Pace"]
            )

        # Streak analysis
        streaks = conn.execute("""
            SELECT
                streak_start,
                streak_end,
                streak_length_days
            FROM streak_analysis
            ORDER BY streak_length_days DESC
            LIMIT 5
        """).fetchall()

        if streaks:
            print_table(
                "Top 5 Running Streaks",
                streaks,
                ["Start Date", "End Date", "Days"]
            )

        # Personal records
        print("\n" + "=" * 80)
        print("Personal Records")
        print("=" * 80)

        # Longest run
        longest = conn.execute("""
            SELECT start_date, distance_miles
            FROM runs_miles
            ORDER BY distance_miles DESC
            LIMIT 1
        """).fetchone()
        if longest:
            print(f"\nLongest Run:       {longest[1]:.2f} miles on {longest[0]}")

        # Fastest pace
        fastest = conn.execute("""
            SELECT start_date, average_pace_min_per_mile, distance_miles
            FROM runs_miles
            WHERE distance_miles >= 3  -- At least 3 miles
            ORDER BY average_pace_min_per_mile ASC
            LIMIT 1
        """).fetchone()
        if fastest:
            print(f"Fastest Pace:      {fastest[1]:.1f} min/mile on {fastest[0]} ({fastest[2]:.1f} mi)")

        # Most distance in a week
        weekly = conn.execute("""
            WITH weekly_totals AS (
                SELECT
                    DATE_TRUNC('week', start_date) as week_start,
                    SUM(distance_miles) as total_miles
                FROM runs_miles
                GROUP BY week_start
            )
            SELECT week_start, total_miles
            FROM weekly_totals
            ORDER BY total_miles DESC
            LIMIT 1
        """).fetchone()
        if weekly:
            print(f"Most Miles/Week:   {weekly[1]:.1f} miles (week of {weekly[0]})")

        # Most runs in a month
        max_month = conn.execute("""
            SELECT start_year, start_month, run_count, total_distance_miles
            FROM monthly_summary_miles
            ORDER BY run_count DESC
            LIMIT 1
        """).fetchone()
        if max_month:
            print(f"Most Runs/Month:   {max_month[2]} runs in {max_month[0]}-{max_month[1]:02d} ({max_month[3]:.1f} miles)")

        print("\n" + "=" * 80)
        print(f"Database: {DUCKDB_FILE.absolute()}")
        print("=" * 80)
        print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception(f"Query failed: {e}")
