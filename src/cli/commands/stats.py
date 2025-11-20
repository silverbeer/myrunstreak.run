"""Stats commands for stk CLI."""

import typer

from cli import api, display


def streak(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Show your current running streak."""
    data = api.request("stats/streaks")

    if json_output:
        import json

        print(json.dumps(data, indent=2))
    else:
        display.display_streak(data)


def overall(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Show overall running statistics."""
    data = api.request("stats/overall")

    if json_output:
        import json

        print(json.dumps(data, indent=2))
    else:
        display.display_overall_stats(data)


def records(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Show personal records."""
    data = api.request("stats/records")

    if json_output:
        import json

        print(json.dumps(data, indent=2))
    else:
        display.display_records(data)


def monthly(
    limit: int = typer.Option(12, "--limit", "-n", help="Number of months"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Show monthly statistics."""
    data = api.request("stats/monthly", {"limit": limit})

    if json_output:
        import json

        print(json.dumps(data, indent=2))
    else:
        display.display_monthly_stats(data)
