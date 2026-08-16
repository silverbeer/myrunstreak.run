"""Delete an imported run (SB-621)."""

from __future__ import annotations

import typer
from rich.console import Console

from cli.api import delete_request, request
from cli.display import display_error

console = Console()


def delete_run(
    activity_id: str = typer.Argument(..., help="Activity id, e.g. gpx-7378842ad231bae2"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt"),
) -> None:
    """Delete one of your imported runs.

    Only imported runs can be deleted: a synced run would be recreated by the
    next sync, so the API refuses those.
    """
    run = request(f"runs/{activity_id}")

    distance = run.get("distance_km") or 0
    console.print(f"[bold]{run.get('date', '')[:10]}[/bold] · {distance:.2f} km · {activity_id}")

    if not run.get("is_imported"):
        display_error("Only imported runs can be deleted.")
        console.print(
            "[dim]A synced run comes back on the next sync — remove it in SmashRun instead.[/dim]"
        )
        raise typer.Exit(1)

    if not yes:
        # Destructive and irreversible: the file would have to be imported
        # again, and the GPS track and splits go with it.
        typer.confirm(
            "Delete this run, its GPS track and its splits?",
            abort=True,
        )

    delete_request(f"runs/{activity_id}")
    console.print("[green]Deleted.[/green] Streak and totals have been recalculated.")
