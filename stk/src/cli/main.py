#!/usr/bin/env python3
"""
stk - MyRunStreak CLI

A terminal-native CLI for tracking your running streak.

Usage:
    stk                  # Show current streak
    stk stats            # Overall statistics
    stk recent           # Recent runs
    stk records          # Personal records
    stk sync             # Sync runs from SmashRun
    stk auth login       # Authenticate with SmashRun
"""

import typer
from rich.console import Console

from cli import __version__
from cli.commands import auth, plan, runs, splits, stats, sync, workout

# Create the main app
app = typer.Typer(
    name="stk",
    help="Track your running streak from the terminal.",
    no_args_is_help=False,
    add_completion=True,
)

# Add command groups
app.add_typer(auth.app, name="auth", help="Authentication commands")
app.add_typer(plan.plan_app, name="plan", help="Adaptive monthly plan")
app.add_typer(plan.constraint_app, name="constraint", help="Plan constraints (travel, injury)")
app.add_typer(plan.readiness_app, name="readiness", help="Daily readiness check-in")
app.add_typer(splits.splits_app, name="splits", help="Per-mile splits")
app.add_typer(workout.workout_app, name="workout", help="Athlete workout tracker")

# Console for output
console = Console()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"stk version {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", callback=version_callback, help="Show version"
    ),
) -> None:
    """
    stk - Track your running streak from the terminal.

    Run without arguments to see your current streak.
    """
    if ctx.invoked_subcommand is None:
        # Default action: show streak
        stats.streak()


# Register commands directly on the app
app.command(name="streak")(stats.streak)
app.command(name="stats")(stats.overall)
app.command(name="recent")(runs.recent)
app.command(name="records")(stats.records)
app.command(name="monthly")(stats.monthly)
app.command(name="runs")(runs.list_runs)
app.command(name="sync")(sync.sync_runs)


def cli() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    cli()
