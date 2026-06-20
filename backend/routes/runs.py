"""/runs and /runs/recent — list endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from backend.auth import authenticate_request
from backend.cache import cached
from fastapi import APIRouter, Depends, Query
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
async def _list_runs(user_id: UUID, offset: int, limit: int) -> dict[str, Any]:
    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)
    runs_data = runs_repo.get_runs_by_user(user_id, limit=limit, offset=offset)

    total_result = (
        supabase.table("runs").select("*", count="exact").eq("user_id", str(user_id)).execute()
    )
    total = total_result.count or 0

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
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    return await _list_runs(user_id, offset, limit)
