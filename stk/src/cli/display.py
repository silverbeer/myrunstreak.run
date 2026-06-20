"""Display utilities for stk CLI with Rich formatting."""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# Conversion factors
KM_TO_MILES = 0.621371


def km_to_miles(km: float) -> float:
    """Convert kilometers to miles."""
    return km * KM_TO_MILES


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return celsius * 9 / 5 + 32


def format_pace(min_per_km: float) -> str:
    """Format pace from min/km to min/mile."""
    min_per_mile = min_per_km / KM_TO_MILES
    minutes = int(min_per_mile)
    seconds = int((min_per_mile - minutes) * 60)
    return f"{minutes}:{seconds:02d}"


def get_flame_art(streak: int) -> str:
    """Get ASCII art flame based on streak length."""
    if streak >= 365:
        # Epic flame for year+ streaks
        return """
    [bold red]     )  (
    [bold yellow]    (   ) )
    [bold red]     ) ( (
    [bold yellow]    (  )  )
    [bold orange1]   .-'''''`-.
    [bold red]  ,'         `.
    [bold orange1] /   [bold white]LEGEND[bold orange1]   \\
    [bold yellow]:    [bold white]{streak:^6}[bold yellow]    :
    [bold orange1] \\           /
    [bold red]  `._______.'
        """.format(streak=f"{streak}d")
    elif streak >= 100:
        # Big flame for 100+ day streaks
        return """
    [bold red]    (  )
    [bold yellow]   (   ) )
    [bold red]    ) ( (
    [bold orange1]   (  )  )
    [bold yellow]  .-'```'-.
    [bold red] ,'       `.
    [bold orange1]/   [bold white]FIRE[bold orange1]   \\
    [bold yellow]:  [bold white]{streak:^7}[bold yellow]  :
    [bold red] `._______.'
        """.format(streak=f"{streak} days")
    elif streak >= 30:
        # Medium flame
        return """
    [bold yellow]   ( )
    [bold orange1]  (   )
    [bold red]   ) (
    [bold yellow] .-'`'-.
    [bold orange1]/  [bold white]HOT[bold orange1]  \\
    [bold red]:  [bold white]{streak:^5}[bold red] :
    [bold yellow] `.___.`
        """.format(streak=f"{streak}d")
    elif streak >= 7:
        # Small flame
        return """
    [bold yellow]  ( )
    [bold orange1] (   )
    [bold red] .-'-.
    [bold yellow]/[bold white]{streak:^5}[bold yellow]\\
    [bold orange1]`---'
        """.format(streak=f"{streak}d")
    elif streak >= 1:
        # Tiny flame
        return f"""
    [bold yellow] ( )
    [bold orange1](   )
    [bold red] \\{streak}/
        """
    else:
        # No streak - sad
        return """
    [dim]  _
    [dim] / \\
    [dim]|   |
    [dim] \\_/
    [dim]  0
        """


def display_streak(data: dict[str, Any]) -> None:
    """Display current streak with ASCII art."""
    current = data.get("current_streak", 0)
    longest = data.get("longest_streak", 0)

    # Build the display
    flame = get_flame_art(current)

    # Create streak text
    if current > 0:
        if current == longest and current >= 7:
            status = "[bold green]NEW RECORD![/bold green]"
        elif current >= longest * 0.8:
            status = f"[yellow]{longest - current} days to record[/yellow]"
        else:
            status = f"Record: {longest} days"

        streak_text = f"""
{flame}
[bold]Current Streak:[/bold] [bold green]{current}[/bold green] days
{status}
        """
    else:
        streak_text = f"""
{flame}
[bold]Streak:[/bold] [red]0 days[/red]
[dim]Get out there and run![/dim]
        """

    console.print(Panel(streak_text, title="[bold cyan]stk[/bold cyan]", border_style="cyan"))

    # Show top streaks if available
    top_streaks = data.get("top_streaks", [])
    if top_streaks and len(top_streaks) > 1:
        table = Table(title="Top Streaks", show_header=True, border_style="dim")
        table.add_column("Start", style="cyan")
        table.add_column("End", style="cyan")
        table.add_column("Days", justify="right", style="green")
        table.add_column("", justify="center")

        for streak in top_streaks[:5]:
            is_current = "[bold yellow]*[/bold yellow]" if streak.get("is_current") else ""
            table.add_row(
                streak.get("start_date", ""),
                streak.get("end_date", ""),
                str(streak.get("length_days", 0)),
                is_current,
            )

        console.print(table)


def display_overall_stats(data: dict[str, Any]) -> None:
    """Display overall running statistics."""
    total_miles = km_to_miles(data.get("total_km", 0))
    avg_miles = km_to_miles(data.get("avg_km", 0))
    longest_miles = km_to_miles(data.get("longest_run_km", 0))
    avg_pace = format_pace(data.get("avg_pace_min_per_km", 0))

    table = Table(title="Overall Statistics", show_header=True, border_style="cyan")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")

    table.add_row("Total Runs", f"{data.get('total_runs', 0):,}")
    table.add_row("Total Distance", f"{total_miles:,.1f} mi")
    table.add_row("Average Distance", f"{avg_miles:.2f} mi")
    table.add_row("Longest Run", f"{longest_miles:.2f} mi")
    table.add_row("Average Pace", f"{avg_pace} /mi")

    console.print(table)


def display_recent_runs(data: dict[str, Any]) -> None:
    """Display recent runs in a table."""
    runs = data.get("runs", [])

    table = Table(
        title=f"Recent Runs ({data.get('count', len(runs))})",
        show_header=True,
        border_style="cyan",
    )
    table.add_column("Date", style="cyan")
    table.add_column("Distance", justify="right", style="green")
    table.add_column("Time", justify="right")
    table.add_column("Pace", justify="right", style="yellow")
    table.add_column("HR", justify="right", style="red")
    table.add_column("Temp", justify="right", style="blue")

    for run in runs:
        distance_miles = km_to_miles(run.get("distance_km", 0))
        pace = format_pace(run.get("avg_pace_min_per_km", 0))
        duration = run.get("duration_minutes", 0)
        hr = run.get("heart_rate_avg")
        temp_c = run.get("temperature_celsius")

        # Format duration
        hours = int(duration // 60)
        mins = int(duration % 60)
        if hours > 0:
            time_str = f"{hours}h {mins}m"
        else:
            time_str = f"{mins}m"

        # Format optional fields
        hr_str = str(int(hr)) if hr else "-"
        temp_str = f"{int(celsius_to_fahrenheit(temp_c))}°" if temp_c else "-"

        table.add_row(
            run.get("date", "")[:10],
            f"{distance_miles:.2f} mi",
            time_str,
            pace,
            hr_str,
            temp_str,
        )

    console.print(table)


def display_monthly_stats(data: dict[str, Any]) -> None:
    """Display monthly statistics."""
    months = data.get("months", [])

    table = Table(
        title=f"Monthly Stats ({data.get('count', len(months))} months)",
        show_header=True,
        border_style="cyan",
    )
    table.add_column("Month", style="cyan")
    table.add_column("Runs", justify="right", style="green")
    table.add_column("Total", justify="right")
    table.add_column("Avg", justify="right")
    table.add_column("Pace", justify="right", style="yellow")

    for month in months:
        total_miles = km_to_miles(month.get("total_km", 0))
        avg_miles = km_to_miles(month.get("avg_km", 0))
        pace = format_pace(month.get("avg_pace_min_per_km", 0))

        table.add_row(
            month.get("month", "")[:7],
            str(month.get("run_count", 0)),
            f"{total_miles:.1f} mi",
            f"{avg_miles:.2f} mi",
            pace,
        )

    console.print(table)


def display_records(data: dict[str, Any]) -> None:
    """Display personal records."""
    table = Table(title="Personal Records", show_header=True, border_style="cyan")
    table.add_column("Record", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Date", style="yellow")

    if "longest_run" in data:
        lr = data["longest_run"]
        distance_miles = km_to_miles(lr.get("distance_km", 0))
        table.add_row("Longest Run", f"{distance_miles:.2f} mi", lr.get("date", ""))

    if "fastest_pace" in data:
        fp = data["fastest_pace"]
        pace = format_pace(fp.get("pace_min_per_km", 0))
        distance_miles = km_to_miles(fp.get("distance_km", 0))
        table.add_row(
            "Fastest Pace (3+ mi)",
            f"{pace} /mi ({distance_miles:.2f} mi)",
            fp.get("date", ""),
        )

    if "most_km_week" in data:
        wk = data["most_km_week"]
        total_miles = km_to_miles(wk.get("total_km", 0))
        table.add_row(
            "Best Week",
            f"{total_miles:.1f} mi",
            f"Week of {wk.get('week_start', '')}",
        )

    if "most_km_month" in data:
        mo = data["most_km_month"]
        total_miles = km_to_miles(mo.get("total_km", 0))
        table.add_row(
            "Best Month",
            f"{total_miles:.1f} mi ({mo.get('run_count', 0)} runs)",
            mo.get("month", "")[:7],
        )

    console.print(table)


def display_sync_progress(message: str, done: bool = False) -> None:
    """Display sync progress message."""
    if done:
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[cyan]→[/cyan] {message}")


def display_error(message: str) -> None:
    """Display error message."""
    console.print(f"[red]✗[/red] {message}")


def display_warning(message: str) -> None:
    """Display warning message."""
    console.print(f"[yellow]![/yellow] {message}")


def display_info(message: str) -> None:
    """Display info message."""
    console.print(f"[dim]ℹ[/dim] {message}")
