"""Import a run from an activity file (SB-99)."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from cli.api import post_file
from cli.display import display_error

console = Console()

# Kept in step with the server's allowlist; the endpoint is still the authority
# and rejects anything else with a 415.
SUPPORTED = (".gpx", ".tcx", ".json")


def import_activity(
    path: Path = typer.Argument(..., help="Activity file: .gpx, .tcx or SmashRun .json"),
    timezone: str = typer.Option(
        "America/New_York",
        "--timezone",
        "-z",
        help="Zone the run happened in — GPX/TCX record UTC, so this decides the run's date",
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Import one run from a GPX, TCX or SmashRun JSON file.

    Idempotent: importing the same file twice reports it as already imported
    rather than creating a second run.
    """
    if not path.is_file():
        display_error(f"No such file: {path}")
        raise typer.Exit(1)
    if path.suffix.lower() not in SUPPORTED:
        display_error(f"{path.suffix or 'That file'} isn't supported. Try: {', '.join(SUPPORTED)}")
        raise typer.Exit(1)

    result = post_file(
        "import/activity",
        filename=path.name,
        content=path.read_bytes(),
        form={"timezone": timezone},
        timeout=60.0,
    )

    if json_output:
        print(json.dumps(result, indent=2))
        return

    distance = result.get("distance_km", 0.0)
    minutes = round(float(result.get("duration_seconds", 0)) / 60, 1)
    started = str(result.get("start_date_time_local", ""))[:16].replace("T", " ")

    if result["status"] == "duplicate":
        console.print(f"[yellow]Already imported[/yellow] — {started}, {distance} km")
        console.print("[dim]Nothing was changed.[/dim]")
        return

    track = "with GPS track" if result.get("has_track") else "no GPS track"
    console.print(f"[green]Imported[/green] {started} — {distance} km in {minutes} min ({track})")
