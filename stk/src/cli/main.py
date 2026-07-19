#!/usr/bin/env python3
"""
stk - MyRunStreak CLI

A terminal-native CLI for tracking your running streak.

Usage:
    stk                  # Morning-glance dashboard (streak, goals, last run)
    stk streak           # Streak + flame art
    stk stats            # Overall statistics
    stk recent           # Recent runs
    stk records          # Personal records
    stk runs             # List runs (filters: --on-this-day, --weather, --sort, ...)
    stk summary          # Aggregate of a filtered set vs overall
    stk goals            # Distance-goal progress
    stk sync             # Sync runs from SmashRun
    stk auth login       # Authenticate with SmashRun
"""

import typer
from rich.console import Console

from cli import __version__
from cli import cache as cache_lib
from cli.commands import athlete, auth, cache, invite, plan, runs, splits, stats, sync, workout

# Create the main app
app = typer.Typer(
    name="stk",
    help="Track your running streak from the terminal. Run bare for the dashboard.",
    epilog=(
        "Examples: [cyan]stk[/cyan] (dashboard) · "
        "[cyan]stk runs --on-this-day today[/cyan] · "
        "[cyan]stk summary --weather rainy[/cyan] · "
        "[cyan]stk runs --sort temperature --order desc -n 5[/cyan]"
    ),
    rich_markup_mode="rich",
    no_args_is_help=False,
    add_completion=True,
)

# Help-panel names (shared so the grouping reads as one system)
_PANEL_STREAK = "Streak & Stats"
_PANEL_RUNS = "Runs"
_PANEL_PLANNING = "Planning & Goals"
_PANEL_COACHING = "Coaching"
_PANEL_SYSTEM = "System"

# Add command groups
app.add_typer(auth.app, name="auth", help="Authentication commands", rich_help_panel=_PANEL_SYSTEM)
app.add_typer(
    plan.plan_app, name="plan", help="Adaptive monthly plan", rich_help_panel=_PANEL_PLANNING
)
app.add_typer(
    plan.constraint_app,
    name="constraint",
    help="Plan constraints (travel, injury)",
    rich_help_panel=_PANEL_PLANNING,
)
app.add_typer(
    plan.readiness_app,
    name="readiness",
    help="Daily readiness check-in",
    rich_help_panel=_PANEL_PLANNING,
)
app.add_typer(
    splits.splits_app, name="splits", help="Per-mile splits", rich_help_panel=_PANEL_STREAK
)
app.add_typer(
    workout.workout_app,
    name="workout",
    help="Athlete workout tracker",
    rich_help_panel=_PANEL_COACHING,
)
app.add_typer(
    invite.invite_app,
    name="invite",
    help="Invite-only onboarding (admin)",
    rich_help_panel=_PANEL_COACHING,
)
app.add_typer(
    athlete.athlete_app,
    name="athlete",
    help="Athletes you coach",
    rich_help_panel=_PANEL_COACHING,
)
app.add_typer(
    cache.cache_app, name="cache", help="Local response cache", rich_help_panel=_PANEL_SYSTEM
)

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
    no_cache: bool = typer.Option(
        False, "--no-cache", help="Bypass the local response cache for this command"
    ),
) -> None:
    """
    stk - Track your running streak from the terminal.

    Run without arguments for the dashboard: streak, goals, last run.
    """
    cache_lib.set_no_cache(no_cache)
    if ctx.invoked_subcommand is None:
        # Default action: the morning-glance dashboard
        stats.dashboard()


# Register commands directly on the app
app.command(name="streak", rich_help_panel=_PANEL_STREAK)(stats.streak)
app.command(name="stats", rich_help_panel=_PANEL_STREAK)(stats.overall)
app.command(name="records", rich_help_panel=_PANEL_STREAK)(stats.records)
app.command(name="monthly", rich_help_panel=_PANEL_STREAK)(stats.monthly)
app.command(name="recent", rich_help_panel=_PANEL_RUNS)(runs.recent)
app.command(name="runs", rich_help_panel=_PANEL_RUNS)(runs.list_runs)
app.command(name="summary", rich_help_panel=_PANEL_RUNS)(runs.summary)
app.command(name="sync", rich_help_panel=_PANEL_RUNS)(sync.sync_runs)
app.command(name="goals", rich_help_panel=_PANEL_PLANNING)(stats.goals)


def cli() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    cli()
