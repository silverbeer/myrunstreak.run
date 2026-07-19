"""Stats commands for stk CLI."""

from datetime import datetime
from typing import Any

import typer

from cli import api, display


def dashboard() -> None:
    """One-screen morning glance (the bare ``stk`` default).

    Streak is required; goals / last run / on-this-day are progressive
    enhancement — a failing optional read (older backend, transient error)
    degrades to a sparser dashboard instead of killing the command. All four
    reads are version-cached, so the repeat cost is zero.
    """
    streak_data = api.request("stats/streaks")

    def _try(endpoint: str, params: dict[str, Any] | None = None) -> Any:
        try:
            return api.request(endpoint, params)
        except SystemExit:  # api.request exits on HTTP/network errors
            return None

    goals_data = _try("stats/goals")
    recent = _try("runs/recent", {"limit": 1})
    otd = _try("runs", {"on_this_day": datetime.now().strftime("%m-%d"), "limit": 1, "offset": 0})

    last_run = (recent or {}).get("runs", [None])[0] if recent else None
    otd_count = (otd or {}).get("total") if otd else None
    display.display_dashboard(streak_data, goals_data, last_run, otd_count)


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


def goals(
    history: bool = typer.Option(
        False, "--history", help="All past goal periods (target vs achieved)"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Show distance-goal progress (current year + month, or full history)."""
    data = api.request("stats/goals/history" if history else "stats/goals")

    if json_output:
        import json

        print(json.dumps(data, indent=2))
    elif history:
        display.display_goal_history(data)
    else:
        display.display_goals(data)
