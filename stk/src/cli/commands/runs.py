"""Runs commands for stk CLI."""

from datetime import datetime
from typing import Any

import typer

from cli import api, display


def _filter_params(**kwargs: Any) -> dict[str, Any]:
    """Drop None-valued params before hitting the API.

    httpx serializes ``None`` query values as empty strings, which FastAPI's
    typed params reject with a 422 — and None-laden dicts would also pollute
    the local cache keys (params are part of the key). Also resolves the
    ``--on-this-day today`` shorthand to the current MM-DD client-side, so the
    cache key stays stable for the whole day.
    """
    if kwargs.get("on_this_day") == "today":
        kwargs["on_this_day"] = datetime.now().strftime("%m-%d")
    return {k: v for k, v in kwargs.items() if v is not None}


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
    limit: int = typer.Option(50, "--limit", "-n", help="Number of runs (max 366)"),
    on_this_day: str | None = typer.Option(
        None, "--on-this-day", help='MM-DD across all years, or "today"'
    ),
    date_from: str | None = typer.Option(
        None, "--date-from", help="Runs on/after this date (YYYY-MM-DD)"
    ),
    date_to: str | None = typer.Option(
        None, "--date-to", help="Runs on/before this date (YYYY-MM-DD)"
    ),
    distance_min: float | None = typer.Option(None, "--distance-min", help="Min distance (km)"),
    distance_max: float | None = typer.Option(None, "--distance-max", help="Max distance (km)"),
    weather: str | None = typer.Option(
        None, "--weather", help="One of: sunny, cloudy, rainy, snowy, windy, hot, cold"
    ),
    temp_min: float | None = typer.Option(None, "--temp-min", help="Min temperature (°C)"),
    temp_max: float | None = typer.Option(None, "--temp-max", help="Max temperature (°C)"),
    pace_min: float | None = typer.Option(
        None, "--pace-min", help="Slower pace bound (min/km — larger number = slower)"
    ),
    pace_max: float | None = typer.Option(
        None, "--pace-max", help="Faster pace bound (min/km — smaller number = faster)"
    ),
    hour_min: int | None = typer.Option(None, "--hour-min", help="Earliest start hour (0-23)"),
    hour_max: int | None = typer.Option(None, "--hour-max", help="Latest start hour (0-23)"),
    sort: str = typer.Option("date", "--sort", help="date|distance|pace|temperature"),
    order: str = typer.Option("desc", "--order", help="asc|desc"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """List runs with pagination, filters, and sorting."""
    params = _filter_params(
        offset=offset,
        limit=limit,
        on_this_day=on_this_day,
        date_from=date_from,
        date_to=date_to,
        distance_min=distance_min,
        distance_max=distance_max,
        weather_type=weather,
        temp_min=temp_min,
        temp_max=temp_max,
        pace_min=pace_min,
        pace_max=pace_max,
        hour_min=hour_min,
        hour_max=hour_max,
        sort=sort,
        order=order,
    )
    data = api.request("runs", params)

    if json_output:
        import json

        print(json.dumps(data, indent=2))
    else:
        total = data.get("total", 0)
        count = data.get("count", 0)
        display.display_info(f"Showing {offset + 1}-{offset + count} of {total}")
        display.display_recent_runs(data)


_AUDIO_TYPES = ("podcast", "music", "audiobook", "other", "none")


def audio(
    activity_id: str = typer.Argument(..., help="Run's activity id (from stk runs)"),
    audio_type: str = typer.Argument(
        ..., help="What you listened to: podcast | music | audiobook | other | none"
    ),
    note: str | None = typer.Option(
        None, "--note", "-m", help='Optional context, e.g. "Noah Kahan playlist today"'
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Record what you listened to on a run (SB-302)."""
    if audio_type not in _AUDIO_TYPES:
        display.display_error(f"audio type must be one of: {', '.join(_AUDIO_TYPES)}")
        raise typer.Exit(1)

    data = api.patch_request(
        f"runs/{activity_id}/audio",
        {"audio_type": audio_type, "audio_note": note},
    )

    if json_output:
        import json

        print(json.dumps(data, indent=2))
    else:
        label = data.get("audio_type") or "cleared"
        extra = f' — "{data["audio_note"]}"' if data.get("audio_note") else ""
        display.display_success(f"🎧 {activity_id}: {label}{extra}")


route_app = typer.Typer(help="Examine a single route + its GPS map")


@route_app.command("show")
def route_show(
    activity_id: str = typer.Argument(..., help="Run's activity id (from stk runs / route URL)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Show a run's GPS route as a braille map + stats."""
    data = api.request(f"runs/{activity_id}/track")

    if json_output:
        import json

        print(json.dumps(data, indent=2))
    else:
        display.display_route_card(data)


def routes(
    min_runs: int = typer.Option(2, "--min-runs", help="Only routes run at least this many times"),
    limit: int = typer.Option(15, "--limit", "-n", help="Max routes to show"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Your most-run routes — how many times you've run each (GPS runs only)."""
    data = api.request("runs/routes", {"min_runs": min_runs})

    if json_output:
        import json

        print(json.dumps(data, indent=2))
    else:
        display.display_route_leaderboard(data, limit=limit)


def summary(
    on_this_day: str | None = typer.Option(
        None, "--on-this-day", help='MM-DD across all years, or "today"'
    ),
    date_from: str | None = typer.Option(
        None, "--date-from", help="Runs on/after this date (YYYY-MM-DD)"
    ),
    date_to: str | None = typer.Option(
        None, "--date-to", help="Runs on/before this date (YYYY-MM-DD)"
    ),
    distance_min: float | None = typer.Option(None, "--distance-min", help="Min distance (km)"),
    distance_max: float | None = typer.Option(None, "--distance-max", help="Max distance (km)"),
    weather: str | None = typer.Option(
        None, "--weather", help="One of: sunny, cloudy, rainy, snowy, windy, hot, cold"
    ),
    temp_min: float | None = typer.Option(None, "--temp-min", help="Min temperature (°C)"),
    temp_max: float | None = typer.Option(None, "--temp-max", help="Max temperature (°C)"),
    pace_min: float | None = typer.Option(
        None, "--pace-min", help="Slower pace bound (min/km — larger number = slower)"
    ),
    pace_max: float | None = typer.Option(
        None, "--pace-max", help="Faster pace bound (min/km — smaller number = faster)"
    ),
    hour_min: int | None = typer.Option(None, "--hour-min", help="Earliest start hour (0-23)"),
    hour_max: int | None = typer.Option(None, "--hour-max", help="Latest start hour (0-23)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Aggregate stats for a filtered set of runs, compared against overall."""
    params = _filter_params(
        on_this_day=on_this_day,
        date_from=date_from,
        date_to=date_to,
        distance_min=distance_min,
        distance_max=distance_max,
        weather_type=weather,
        temp_min=temp_min,
        temp_max=temp_max,
        pace_min=pace_min,
        pace_max=pace_max,
        hour_min=hour_min,
        hour_max=hour_max,
    )
    data = api.request("runs/summary", params)

    if json_output:
        import json

        print(json.dumps(data, indent=2))
    else:
        display.display_summary(data)
