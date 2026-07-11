"""/runs and /runs/recent — list endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from backend.auth import authenticate_request
from backend.cache import cached
from fastapi import APIRouter, Depends, HTTPException, Query, status
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import RunsRepository

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


@cached(ttl=60, key_prefix="runs:list")
async def _list_runs(
    user_id: UUID,
    offset: int,
    limit: int,
    date_from: date | None = None,
    date_to: date | None = None,
    distance_min: float | None = None,
    distance_max: float | None = None,
) -> dict[str, Any]:
    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)
    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "distance_min": distance_min,
        "distance_max": distance_max,
    }
    runs_data = runs_repo.get_runs_by_user(user_id, limit=limit, offset=offset, **filters)
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
) -> dict[str, Any]:
    return await _list_runs(user_id, offset, limit, date_from, date_to, distance_min, distance_max)


# NOTE: registered after /recent and "" so the static paths keep priority.
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

    splits = [
        {
            "split_number": s["split_number"],
            "split_unit": s.get("split_unit"),
            "cumulative_distance_km": _f(s.get("cumulative_distance_km")),
            "cumulative_seconds": _f(s.get("cumulative_seconds")),
            "pace_min_per_km": _f(s.get("pace_min_per_km")),
            "heart_rate": s.get("heart_rate"),
            "elevation_gain_m": _f(s.get("cumulative_elevation_gain_meters")),
            "elevation_loss_m": _f(s.get("cumulative_elevation_loss_meters")),
        }
        for s in sorted(
            repo.get_splits_for_run(UUID(run["id"])), key=lambda s: s["split_number"] or 0
        )
    ]

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
