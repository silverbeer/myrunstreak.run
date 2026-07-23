"""/runs and /runs/recent — list endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from backend.auth import authenticate_request
from backend.cache import cached
from backend.routes.sync import _resolve_access_token
from fastapi import APIRouter, Depends, HTTPException, Query, status
from src.shared.smashrun import SmashRunAPIClient
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import RunsRepository, TokenRepository

router = APIRouter(prefix="/runs", tags=["runs"])


@cached(ttl=60, key_prefix="runs:recent")
async def _recent(user_id: UUID, limit: int) -> dict[str, Any]:
    supabase = get_supabase_client()
    runs_data = RunsRepository(supabase).get_runs_by_user(user_id, limit=limit, offset=0)
    runs = [
        {
            "activity_id": r["source_activity_id"],
            "date": r["start_date_time_local"],
            "distance_km": float(r["distance_km"]),
            "duration_seconds": float(r["duration_seconds"]),
            "duration_minutes": round(float(r["duration_seconds"]) / 60, 1),
            "avg_pace_min_per_km": (
                float(r["average_pace_min_per_km"]) if r["average_pace_min_per_km"] else None
            ),
            "heart_rate_avg": r.get("heart_rate_average"),
            "temperature_celsius": r.get("temperature_celsius"),
            "weather": r.get("weather_type"),
        }
        for r in runs_data
    ]
    return {"count": len(runs), "runs": runs}


@router.get("/recent")
async def get_recent_runs(
    user_id: UUID = Depends(authenticate_request),
    limit: int = Query(10, ge=1, le=100),
) -> dict[str, Any]:
    return await _recent(user_id, limit)


# Whitelist for the sort param -> actual column (SB-269).
_SORT_COLUMNS = {
    "date": "start_date_time_local",
    "distance": "distance_km",
    "pace": "average_pace_min_per_km",
    "temperature": "temperature_celsius",
}


@cached(ttl=60, key_prefix="runs:list")
async def _list_runs(
    user_id: UUID,
    offset: int,
    limit: int,
    date_from: date | None = None,
    date_to: date | None = None,
    distance_min: float | None = None,
    distance_max: float | None = None,
    weather_type: str | None = None,
    temp_min: float | None = None,
    temp_max: float | None = None,
    pace_min: float | None = None,
    pace_max: float | None = None,
    on_this_day: str | None = None,
    hour_min: int | None = None,
    hour_max: int | None = None,
    sort: str = "date",
    order: str = "desc",
) -> dict[str, Any]:
    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)
    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "distance_min": distance_min,
        "distance_max": distance_max,
        "weather_type": weather_type,
        "temp_min": temp_min,
        "temp_max": temp_max,
        "pace_min": pace_min,
        "pace_max": pace_max,
        "on_this_day": on_this_day,
        "hour_min": hour_min,
        "hour_max": hour_max,
    }
    sort_by = _SORT_COLUMNS.get(sort, "start_date_time_local")
    sort_desc = order != "asc"
    runs_data = runs_repo.get_runs_by_user(
        user_id, limit=limit, offset=offset, sort_by=sort_by, sort_desc=sort_desc, **filters
    )
    total = runs_repo.count_runs_by_user(user_id, **filters)

    runs = [
        {
            "activity_id": r["source_activity_id"],
            "date": r["start_date_time_local"],
            "distance_km": float(r["distance_km"]),
            "duration_minutes": round(float(r["duration_seconds"]) / 60, 1),
            "avg_pace_min_per_km": (
                float(r["average_pace_min_per_km"]) if r["average_pace_min_per_km"] else None
            ),
            "weather": r.get("weather_type"),
            "temperature_celsius": (
                float(r["temperature_celsius"]) if r.get("temperature_celsius") else None
            ),
        }
        for r in runs_data
    ]
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "count": len(runs),
        "runs": runs,
    }


@router.get("")
async def list_runs(
    user_id: UUID = Depends(authenticate_request),
    offset: int = Query(0, ge=0),
    # 366 = a full streak-year (one run/day) in a single page (SB-184).
    limit: int = Query(50, ge=1, le=366),
    date_from: date | None = Query(None, description="Runs on/after this date (inclusive)"),
    date_to: date | None = Query(None, description="Runs on/before this date (inclusive)"),
    distance_min: float | None = Query(None, ge=0, description="Min distance in km"),
    distance_max: float | None = Query(None, ge=0, description="Max distance in km"),
    weather_type: str | None = Query(None, description="Exact weather condition"),
    temp_min: float | None = Query(None, description="Min temperature (C)"),
    temp_max: float | None = Query(None, description="Max temperature (C)"),
    pace_min: float | None = Query(None, ge=0, description="Min pace (min/km) — slower bound"),
    pace_max: float | None = Query(None, ge=0, description="Max pace (min/km) — faster bound"),
    on_this_day: str | None = Query(
        None, pattern=r"^\d{2}-\d{2}$", description="MM-DD across all years (SB-269)"
    ),
    hour_min: int | None = Query(None, ge=0, le=23, description="Earliest start hour (SB-270)"),
    hour_max: int | None = Query(None, ge=0, le=23, description="Latest start hour (SB-270)"),
    sort: str = Query("date", pattern="^(date|distance|pace|temperature)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
) -> dict[str, Any]:
    return await _list_runs(
        user_id,
        offset,
        limit,
        date_from,
        date_to,
        distance_min,
        distance_max,
        weather_type,
        temp_min,
        temp_max,
        pace_min,
        pace_max,
        on_this_day,
        hour_min,
        hour_max,
        sort,
        order,
    )


@cached(ttl=60, key_prefix="runs:summary")
async def _summary(user_id: UUID, **filters: Any) -> dict[str, Any]:
    repo = RunsRepository(get_supabase_client())
    summary = repo.summarize_runs(user_id, **{k: v for k, v in filters.items() if v is not None})
    overall = repo.summarize_runs(user_id)
    summary["overall_avg_pace_min_per_km"] = overall["avg_pace_min_per_km"]
    return summary


@router.get("/summary")
async def runs_summary(
    user_id: UUID = Depends(authenticate_request),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    distance_min: float | None = Query(None, ge=0),
    distance_max: float | None = Query(None, ge=0),
    weather_type: str | None = Query(None),
    temp_min: float | None = Query(None),
    temp_max: float | None = Query(None),
    pace_min: float | None = Query(None, ge=0),
    pace_max: float | None = Query(None, ge=0),
    on_this_day: str | None = Query(None, pattern=r"^\d{2}-\d{2}$"),
    hour_min: int | None = Query(None, ge=0, le=23),
    hour_max: int | None = Query(None, ge=0, le=23),
) -> dict[str, Any]:
    """Aggregate of the filtered set vs overall — the conditions-impact readout
    ("runs above 75% humidity: 22s/mi slower"). SB-269."""
    return await _summary(
        user_id,
        date_from=date_from,
        date_to=date_to,
        distance_min=distance_min,
        distance_max=distance_max,
        weather_type=weather_type,
        temp_min=temp_min,
        temp_max=temp_max,
        pace_min=pace_min,
        pace_max=pace_max,
        on_this_day=on_this_day,
        hour_min=hour_min,
        hour_max=hour_max,
    )


@cached(ttl=60, key_prefix="runs:head")
async def _head(user_id: UUID) -> dict[str, Any]:
    return RunsRepository(get_supabase_client()).get_runs_head(user_id)


@router.get("/head")
async def runs_head(
    user_id: UUID = Depends(authenticate_request),
) -> dict[str, Any]:
    """Cheap version token for the caller's run history — ``{count,
    latest_run_date}``. Clients (the ``stk`` CLI) hit this once per invocation
    and gate their local response cache on the pair: unchanged → serve from
    cache, changed → a run was added/removed → refetch. Cleared alongside the
    other run caches whenever a sync invalidates the user (SB run cache)."""
    return await _head(user_id)


@cached(ttl=60, key_prefix="runs:routes")
async def _routes(user_id: UUID, min_runs: int) -> dict[str, Any]:
    repo = RunsRepository(get_supabase_client())
    routes = repo.get_route_leaderboard(user_id, min_runs=min_runs)
    return {"count": len(routes), "routes": routes}


@router.get("/routes")
async def route_leaderboard(
    user_id: UUID = Depends(authenticate_request),
    min_runs: int = Query(2, ge=1, le=100, description="Only routes run at least this many times"),
) -> dict[str, Any]:
    """Repeated-route leaderboard (SB-291): GPS runs grouped by start cell +
    distance bucket, sorted by run count. Answers "how many times have I run
    this route". Treadmill / no-GPS runs are excluded."""
    return await _routes(user_id, min_runs)


@cached(ttl=86400, key_prefix="runs:track")
async def _track(user_id: UUID, activity_id: str) -> dict[str, Any]:
    supabase = get_supabase_client()
    run = RunsRepository(supabase).get_run_by_activity_id(user_id, activity_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")

    # The GPS track lives only in SmashRun's per-activity detail (recordingValues),
    # not our DB — fetch it on demand with the user's token.
    token = _resolve_access_token(user_id, TokenRepository(supabase))
    with SmashRunAPIClient(access_token=token) as api:
        detail = api.get_activity_by_id(activity_id)

    keys = detail.get("recordingKeys") or []
    values = detail.get("recordingValues") or []
    lat: list[float] = []
    lon: list[float] = []
    if "latitude" in keys and "longitude" in keys and values:
        lat = [float(v) for v in values[keys.index("latitude")]]
        lon = [float(v) for v in values[keys.index("longitude")]]

    # How many times this route has been run (count + rank), so the card can say
    # "run N times, #k of M" (SB-296). Needs the run's own start coords.
    route = None
    run_lat, run_lon, run_dist = (
        run.get("start_latitude"),
        run.get("start_longitude"),
        run.get("distance_km"),
    )
    if run_lat is not None and run_lon is not None and run_dist is not None:
        route = RunsRepository(supabase).get_route_for_run(
            user_id, float(run_lat), float(run_lon), float(run_dist)
        )

    return {
        "activity_id": activity_id,
        "has_track": bool(lat),
        "lat": lat,
        "lon": lon,
        "city": detail.get("city"),
        "state": detail.get("state"),
        "date": run["start_date_time_local"],
        "distance_km": _f(run.get("distance_km")),
        "duration_seconds": _f(run.get("duration_seconds")),
        "avg_pace_min_per_km": _f(run.get("average_pace_min_per_km")),
        "weather_type": run.get("weather_type"),
        "temperature_celsius": _f(run.get("temperature_celsius")),
        "route": route,
    }


@router.get("/{activity_id}/track")
async def get_run_track(
    activity_id: str,
    user_id: UUID = Depends(authenticate_request),
) -> dict[str, Any]:
    """GPS track (lat/lon arrays) + place/stats for one run (SB-293), for the
    `stk route show` braille map. Track is fetched on demand from SmashRun's
    detail payload (not stored). 404 if the run isn't the caller's."""
    return await _track(user_id, activity_id)


# NOTE: registered after /recent, /head, /routes, and "" so the static paths keep priority.
@router.get("/{activity_id}")
async def get_run_detail(
    activity_id: str,
    user_id: UUID = Depends(authenticate_request),
) -> dict[str, Any]:
    """One run with everything interesting about it: weather, vitals, splits,
    and per-split elevation (SB-263 run detail view)."""
    repo = RunsRepository(get_supabase_client())
    run = repo.get_run_by_activity_id(user_id, activity_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")

    splits: list[dict[str, Any]] = []
    prev_km, prev_sec = 0.0, 0.0
    for s in sorted(repo.get_splits_for_run(UUID(run["id"])), key=lambda s: s["split_number"] or 0):
        cum_km = _f(s.get("cumulative_distance_km"))
        cum_sec = _f(s.get("cumulative_seconds"))
        # Splits store only cumulative metrics; per-split pace is derived from
        # the deltas (the stored pace column is unpopulated by sync).
        pace = _f(s.get("pace_min_per_km"))
        if pace is None and cum_km is not None and cum_sec is not None:
            delta_km = cum_km - prev_km
            delta_sec = cum_sec - prev_sec
            if delta_km > 0.001 and delta_sec > 0:
                pace = round(delta_sec / 60 / delta_km, 2)
        if cum_km is not None:
            prev_km = cum_km
        if cum_sec is not None:
            prev_sec = cum_sec
        splits.append(
            {
                "split_number": s["split_number"],
                "split_unit": s.get("split_unit"),
                "cumulative_distance_km": cum_km,
                "cumulative_seconds": cum_sec,
                "pace_min_per_km": pace,
                "heart_rate": s.get("heart_rate"),
                "elevation_gain_m": _f(s.get("cumulative_elevation_gain_meters")),
                "elevation_loss_m": _f(s.get("cumulative_elevation_loss_meters")),
            }
        )

    return {
        "activity_id": run["source_activity_id"],
        "date": run["start_date_time_local"],
        "distance_km": _f(run["distance_km"]),
        "duration_seconds": _f(run["duration_seconds"]),
        "avg_pace_min_per_km": _f(run.get("average_pace_min_per_km")),
        "weather": {
            "temperature_celsius": _f(run.get("temperature_celsius")),
            "weather_type": run.get("weather_type"),
            "humidity_percent": run.get("humidity_percent"),
            "wind_speed_kph": run.get("wind_speed_kph"),
        },
        "vitals": {
            "heart_rate_avg": _f(run.get("heart_rate_average")),
            "heart_rate_min": _f(run.get("heart_rate_min")),
            "heart_rate_max": _f(run.get("heart_rate_max")),
            "cadence_avg": _f(run.get("cadence_average")),
        },
        "how_felt": run.get("how_felt"),
        "notes": run.get("notes"),
        "splits": splits,
    }


def _f(value: Any) -> float | None:
    """Numeric column (str/Decimal from supabase) -> float, preserving None."""
    return float(value) if value is not None else None
