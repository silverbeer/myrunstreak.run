"""Display utilities for stk CLI with Rich formatting."""

from datetime import date, datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# Conversion factors
KM_TO_MILES = 0.621371

WEATHER_EMOJI = {
    "sunny": "☀️",
    "cloudy": "☁️",
    "rainy": "🌧️",
    "snowy": "❄️",
    "windy": "💨",
    "hot": "🥵",
    "cold": "🥶",
}

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _friendly_date(iso: str) -> str:
    """'2026-07-18T13:33:00+00:00' → 'Sat today' / 'Fri yesterday' / 'Sun 7/13'."""
    try:
        d = datetime.fromisoformat(iso).date()
    except ValueError:
        return iso[:10]
    day = _WEEKDAYS[d.weekday()]
    delta = (date.today() - d).days
    if delta == 0:
        return f"{day} [bold green]today[/bold green]"
    if delta == 1:
        return f"{day} [green]yesterday[/green]"
    return f"{day} {d.month}/{d.day}"


def _bar(value: float, max_value: float, width: int = 8, char: str = "▉") -> str:
    """Scale value to a bar of up to `width` chars (at least 1 for non-zero)."""
    if max_value <= 0 or value <= 0:
        return ""
    n = max(1, round(value / max_value * width))
    return char * n


def _progress_bar(percent: float | None, width: int = 16) -> str:
    """▓▓▓▓░░░░ progress bar for a 0-100+ percent (capped at full)."""
    if percent is None:
        return "░" * width
    filled = min(width, round(percent / 100 * width))
    return "▓" * filled + "░" * (width - filled)


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
    """Display runs in a table: friendly dates, distance bars, weather, totals."""
    runs = data.get("runs", [])

    table = Table(
        title=f"Recent Runs ({data.get('count', len(runs))})",
        show_header=True,
        border_style="cyan",
    )
    table.add_column("Date", style="cyan")
    table.add_column("Distance", justify="right", style="green")
    table.add_column("", justify="left", style="green")  # distance bar
    table.add_column("Time", justify="right")
    table.add_column("Pace", justify="right", style="yellow")
    table.add_column("HR", justify="right", style="red")
    table.add_column("Temp", justify="right", style="blue")

    max_km = max((r.get("distance_km") or 0 for r in runs), default=0)
    paces = [r["avg_pace_min_per_km"] for r in runs if r.get("avg_pace_min_per_km")]
    fastest = min(paces, default=None)

    total_km = 0.0
    total_minutes = 0.0
    for run in runs:
        km = run.get("distance_km", 0)
        distance_miles = km_to_miles(km)
        duration = run.get("duration_minutes", 0)
        hr = run.get("heart_rate_avg")
        temp_c = run.get("temperature_celsius")
        total_km += km or 0
        total_minutes += duration or 0

        # Format duration
        hours = int(duration // 60)
        mins = int(duration % 60)
        time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

        # Highlight the fastest pace in the window
        raw_pace = run.get("avg_pace_min_per_km")
        pace = format_pace(raw_pace or 0)
        if raw_pace is not None and raw_pace == fastest and len(paces) > 1:
            pace = f"[bold bright_green]{pace} ⚡[/bold bright_green]"

        # Format optional fields
        hr_str = str(int(hr)) if hr else "-"
        weather = WEATHER_EMOJI.get(run.get("weather") or "", "")
        temp_str = (
            f"{weather} {int(celsius_to_fahrenheit(temp_c))}°".strip() if temp_c else weather or "-"
        )

        table.add_row(
            _friendly_date(run.get("date", "")),
            f"{distance_miles:.2f} mi",
            _bar(km or 0, max_km),
            time_str,
            pace,
            hr_str,
            temp_str,
        )

    # Totals footer for the shown window (display-layer arithmetic only)
    if len(runs) > 1:
        hours = int(total_minutes // 60)
        mins = int(total_minutes % 60)
        table.add_section()
        table.add_row(
            f"[bold]{len(runs)} runs[/bold]",
            f"[bold]{km_to_miles(total_km):.1f} mi[/bold]",
            "",
            f"[bold]{hours}h {mins}m[/bold]" if hours else f"[bold]{mins}m[/bold]",
            "",
            "",
            "",
        )

    console.print(table)


def display_monthly_stats(data: dict[str, Any]) -> None:
    """Display monthly statistics with a mileage trend bar, oldest month first."""
    months = list(reversed(data.get("months", [])))

    table = Table(
        title=f"Monthly Stats ({data.get('count', len(months))} months)",
        show_header=True,
        border_style="cyan",
    )
    table.add_column("Month", style="cyan")
    table.add_column("Runs", justify="right", style="green")
    table.add_column("Total", justify="right")
    table.add_column("Trend", justify="left", style="magenta")
    table.add_column("Avg", justify="right")
    table.add_column("Pace", justify="right", style="yellow")

    max_km = max((m.get("total_km") or 0 for m in months), default=0)
    for month in months:
        total_km = month.get("total_km", 0)
        total_miles = km_to_miles(total_km)
        avg_miles = km_to_miles(month.get("avg_km", 0))
        pace = format_pace(month.get("avg_pace_min_per_km", 0))

        table.add_row(
            month.get("month", "")[:7],
            str(month.get("run_count", 0)),
            f"{total_miles:.1f} mi",
            _bar(total_km or 0, max_km, width=14),
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


def display_summary(data: dict[str, Any]) -> None:
    """Display a filtered-runs aggregate vs overall (the conditions-impact readout)."""
    count = data.get("count", 0)
    total_miles = km_to_miles(data.get("total_km", 0))

    table = Table(title=f"Run Summary ({count} runs)", show_header=True, border_style="cyan")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Runs", str(count))
    table.add_row("Total", f"{total_miles:.1f} mi")

    pace = data.get("avg_pace_min_per_km")
    overall = data.get("overall_avg_pace_min_per_km")
    if pace is not None:
        table.add_row("Avg Pace", f"{format_pace(pace)} /mi")
    if pace is not None and overall is not None:
        # Delta in sec/mi — the arithmetic lives here, not in any narration layer.
        delta_sec = round((pace - overall) / KM_TO_MILES * 60)
        vs = f"{abs(delta_sec)}s/mi {'slower' if delta_sec > 0 else 'faster'} than overall"
        table.add_row("vs Overall", f"{format_pace(overall)} /mi ({vs})")

    console.print(table)


def _calendar_percent(period: str, today: date) -> float:
    """How far through the period the calendar is, 0-100."""
    if period == "year":
        year_days = (date(today.year + 1, 1, 1) - date(today.year, 1, 1)).days
        return today.timetuple().tm_yday / year_days * 100
    # month
    next_month = date(today.year + (today.month == 12), today.month % 12 + 1, 1)
    month_days = (next_month - date(today.year, today.month, 1)).days
    return today.day / month_days * 100


def _vs_calendar(pct: float | None, period: str) -> str:
    """▲/▼ marker: goal percent vs how far through the period the calendar is."""
    if pct is None:
        return ""
    delta = pct - _calendar_percent(period, date.today())
    if delta >= 0:
        return f"[green]▲ +{delta:.0f}% vs calendar[/green]"
    return f"[red]▼ {delta:.0f}% vs calendar[/red]"


def _goal_row(table: Table, label: str, goal: dict[str, Any] | None, period: str) -> None:
    """Add one GoalProgress payload (already in miles) to a goals table."""
    if goal is None:
        table.add_row(label, "-", "-", "", "-", "[dim]no goal set[/dim]")
        return
    pct = goal.get("percent")
    table.add_row(
        label,
        f"{goal.get('goal_mi', 0):.0f} mi",
        f"{goal.get('progress_mi', 0):.1f} mi",
        _progress_bar(pct),
        f"{pct:.1f}%" if pct is not None else "-",
        _vs_calendar(pct, period),
    )


def display_goals(data: dict[str, Any]) -> None:
    """Display current-year and current-month goal progress."""
    table = Table(title="Distance Goals", show_header=True, border_style="cyan")
    table.add_column("Period", style="cyan")
    table.add_column("Target", justify="right")
    table.add_column("Progress", justify="right", style="green")
    table.add_column("", justify="left")
    table.add_column("%", justify="right", style="yellow")
    table.add_column("Pace", justify="left")

    _goal_row(table, "Year", data.get("yearly"), "year")
    _goal_row(table, "Month", data.get("monthly"), "month")
    console.print(table)


def display_goal_history(data: list[dict[str, Any]]) -> None:
    """Display every goal period: target vs achieved, hit/miss."""
    table = Table(title="Goal History", show_header=True, border_style="cyan")
    table.add_column("Period", style="cyan")
    table.add_column("Target", justify="right")
    table.add_column("Achieved", justify="right", style="green")
    table.add_column("%", justify="right", style="yellow")
    table.add_column("Hit", justify="center")

    for goal in data:
        year = goal.get("year", "")
        month = goal.get("month")
        period = f"{year}" if month is None else f"{year}-{int(month):02d}"
        pct = goal.get("percent")
        table.add_row(
            period,
            f"{goal.get('goal_mi', 0):.0f} mi",
            f"{goal.get('progress_mi', 0):.1f} mi",
            f"{pct:.1f}%" if pct is not None else "-",
            "[green]✓[/green]" if goal.get("hit") else "[red]✗[/red]",
        )

    console.print(table)


def display_dashboard(
    streak_data: dict[str, Any],
    goals_data: dict[str, Any] | None,
    last_run: dict[str, Any] | None,
    on_this_day_count: int | None,
) -> None:
    """One-screen morning glance: streak, goals, last run, on-this-day."""
    current = streak_data.get("current_streak", 0)
    streak_miles = km_to_miles(streak_data.get("current_streak_km", 0))
    start = ""
    for s in streak_data.get("top_streaks", []):
        if s.get("is_current"):
            start = s.get("start_date", "")
            break

    lines: list[str] = [
        "",
        f"        [bold red]🔥 DAY {current:,} 🔥[/bold red]",
        f"   [dim]since {start} · {streak_miles:,.0f} mi[/dim]" if start else "",
        "",
    ]

    def goal_line(label: str, goal: dict[str, Any] | None, period: str) -> str | None:
        if goal is None:
            return None
        pct = goal.get("percent")
        return (
            f" {label:<6}{_progress_bar(pct)} "
            f"{goal.get('progress_mi', 0):.0f}/{goal.get('goal_mi', 0):.0f} mi  "
            f"{_vs_calendar(pct, period)}"
        )

    if goals_data:
        today = date.today()
        month_name = today.strftime("%B")
        for line in (
            goal_line(month_name, goals_data.get("monthly"), "month"),
            goal_line(str(today.year), goals_data.get("yearly"), "year"),
        ):
            if line:
                lines.append(line)
        lines.append("")

    if last_run:
        mi = km_to_miles(last_run.get("distance_km", 0))
        pace = format_pace(last_run.get("avg_pace_min_per_km") or 0)
        temp_c = last_run.get("temperature_celsius")
        weather = WEATHER_EMOJI.get(last_run.get("weather") or "", "")
        temp = f" · {weather} {int(celsius_to_fahrenheit(temp_c))}°" if temp_c else ""
        lines.append(
            f" [bold]Last run[/bold]   {_friendly_date(last_run.get('date', ''))} · "
            f"{mi:.2f} mi · {pace} /mi{temp}"
        )

    if on_this_day_count:
        lines.append(
            f" [bold]This day[/bold]   {on_this_day_count} year"
            f"{'s' if on_this_day_count != 1 else ''} of runs on this date"
        )

    lines.append("")
    console.print(
        Panel("\n".join(line for line in lines if line is not None), border_style="cyan", width=64)
    )


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
