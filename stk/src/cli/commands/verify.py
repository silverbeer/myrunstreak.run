"""Reconcile stored runs against SmashRun (SB-477)."""

import json
from datetime import date, timedelta

import typer
from rich.console import Console

from cli import display
from cli.api import request

console = Console()


def verify(
    since: str = typer.Option(None, "--from", help="Start date (YYYY-MM-DD), default 30 days ago"),
    until: str = typer.Option(None, "--to", help="End date (YYYY-MM-DD), default today"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Check stored runs still match SmashRun — the source of record.

    Sync only moves forward, so a run corrected in SmashRun after it synced keeps
    its old value here forever. This finds those, plus runs missing on either
    side. Read-only. Exits 1 when anything is off, so it can gate a cron or CI.
    """
    params: dict[str, str] = {}
    params["until"] = until or date.today().isoformat()
    params["since"] = (
        since or (date.fromisoformat(params["until"]) - timedelta(days=30)).isoformat()
    )

    data = request("verify", params)

    if json_output:
        print(json.dumps(data, indent=2))
    else:
        display.display_verify_report(data)

    if not data.get("clean", True):
        raise typer.Exit(1)
