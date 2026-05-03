"""/stats/* — aggregations over a user's runs.

Lifted from src/lambdas/query_runs/handler.py. All endpoints are JWT-gated;
heavy ones are wrapped in @cached.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from backend.auth import authenticate_request
from backend.cache import cached
from fastapi import APIRouter, Depends, Query
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import RunsRepository

router = APIRouter(prefix="/stats", tags=["stats"])


@cached(ttl=60, key_prefix="stats:overall")
async def _overall_stats(user_id: UUID) -> dict[str, Any]:
    supabase = get_supabase_client()
    return RunsRepository(supabase).get_user_overall_stats(user_id)


@router.get("/overall")
async def get_overall_stats(
    user_id: UUID = Depends(authenticate_request),
) -> dict[str, Any]:
    return await _overall_stats(user_id)


@cached(ttl=60, key_prefix="stats:streaks")
async def _streaks(user_id: UUID) -> dict[str, Any]:
    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)
    current_streak = runs_repo.get_current_streak(user_id)
    return {
        "current_streak": current_streak,
        "longest_streak": current_streak,  # TODO: compute longest properly
        "top_streaks": [
            {
                "start_date": None,
                "end_date": None,
                "length_days": current_streak,
                "is_current": True,
            }
        ]
        if current_streak > 0
        else [],
    }


@router.get("/streaks")
async def get_streaks(
    user_id: UUID = Depends(authenticate_request),
) -> dict[str, Any]:
    return await _streaks(user_id)


@cached(ttl=300, key_prefix="stats:monthly")
async def _monthly(user_id: UUID, limit: int) -> dict[str, Any]:
    supabase = get_supabase_client()
    monthly_data = RunsRepository(supabase).get_monthly_stats(user_id, limit=limit)
    months = [
        {
            "month": f"{m['start_year']}-{m['start_month']:02d}-01",
            "run_count": m["run_count"],
            "total_km": float(m["total_km"]),
            "avg_km": float(m["avg_km"]),
            "avg_pace_min_per_km": float(m["avg_pace"]) if m["avg_pace"] else None,
        }
        for m in monthly_data
    ]
    return {"count": len(months), "months": months}


@router.get("/monthly")
async def get_monthly_stats(
    user_id: UUID = Depends(authenticate_request),
    limit: int = Query(12, ge=1, le=60),
) -> dict[str, Any]:
    return await _monthly(user_id, limit)


@cached(ttl=300, key_prefix="stats:records")
async def _records(user_id: UUID) -> dict[str, Any]:
    supabase = get_supabase_client()
    records: dict[str, Any] = {}

    longest_result = (
        supabase.table("runs")
        .select("start_date, distance_km, source_activity_id")
        .eq("user_id", str(user_id))
        .order("distance_km", desc=True)
        .limit(1)
        .execute()
    )
    longest_data = cast(list[dict[str, Any]], longest_result.data)
    if longest_data:
        r = longest_data[0]
        records["longest_run"] = {
            "date": r["start_date"],
            "distance_km": float(r["distance_km"]),
            "activity_id": r["source_activity_id"],
        }

    fastest_result = (
        supabase.table("runs")
        .select("start_date, average_pace_min_per_km, distance_km, source_activity_id")
        .eq("user_id", str(user_id))
        .gte("distance_km", 5)
        .order("average_pace_min_per_km", desc=False)
        .limit(1)
        .execute()
    )
    fastest_data = cast(list[dict[str, Any]], fastest_result.data)
    if fastest_data:
        r = fastest_data[0]
        records["fastest_pace"] = {
            "date": r["start_date"],
            "pace_min_per_km": float(r["average_pace_min_per_km"]),
            "distance_km": float(r["distance_km"]),
            "activity_id": r["source_activity_id"],
        }

    monthly_result = (
        supabase.table("monthly_summary")
        .select("start_year, start_month, run_count, total_km")
        .eq("user_id", str(user_id))
        .order("total_km", desc=True)
        .limit(1)
        .execute()
    )
    monthly_data = cast(list[dict[str, Any]], monthly_result.data)
    if monthly_data:
        m = monthly_data[0]
        records["most_km_month"] = {
            "month": f"{m['start_year']}-{m['start_month']:02d}-01",
            "run_count": m["run_count"],
            "total_km": float(m["total_km"]),
        }

    return records


@router.get("/records")
async def get_records(
    user_id: UUID = Depends(authenticate_request),
) -> dict[str, Any]:
    return await _records(user_id)
