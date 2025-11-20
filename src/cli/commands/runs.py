"""Runs commands for stk CLI."""

import typer

from cli import api, display


def recent(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of runs"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Show recent runs."""
    data = api.request("runs/recent", {"limit": limit})

    if json_output:
        import json

        print(json.dumps(data, indent=2))
    else:
        display.display_recent_runs(data)


def list_runs(
    offset: int = typer.Option(0, "--offset", "-o", help="Pagination offset"),
    limit: int = typer.Option(50, "--limit", "-n", help="Number of runs"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """List all runs with pagination."""
    data = api.request("runs", {"offset": offset, "limit": limit})

    if json_output:
        import json

        print(json.dumps(data, indent=2))
    else:
        total = data.get("total", 0)
        count = data.get("count", 0)
        display.display_info(f"Showing {offset + 1}-{offset + count} of {total}")
        display.display_recent_runs(data)
