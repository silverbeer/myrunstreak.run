"""/stats/* — aggregations over a user's runs.

All endpoints are JWT-gated; heavy ones are wrapped in @cached.
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from backend.auth import authenticate_request
from backend.cache import cached
from backend.goals import build_goal_history, build_goals_block
from backend.splits_analysis import analyze_run, summarize
from backend.streaks import Streak, compute_streaks
from fastapi import APIRouter, Depends, Query
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import GoalsRepository, RunsRepository, TokenRepository

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

    # Pull every run-date for this user. PostgREST caps a single response at
    # its server-side `db-max-rows` (~1000) regardless of the client `.limit`,
    # so a lone query silently truncates to the oldest ~1000 runs — which drops
    # every recent run and makes the current streak read as 0 (SB-209). Page
    # with .range() until exhausted so compute_streaks sees the full history.
    data: list[dict[str, Any]] = []
    page = 1000
    offset = 0
    while True:
        batch = cast(
            list[dict[str, Any]],
            (
                supabase.table("runs")
                .select("start_date,distance_km")
                .eq("user_id", str(user_id))
                .order("start_date", desc=False)
                .range(offset, offset + page - 1)
                .execute()
            ).data,
        )
        data.extend(batch)
        if len(batch) < page:
            break
        offset += page
    run_dates = [date.fromisoformat(r["start_date"]) for r in data]

    # Sum distance per day so we can total the mileage inside any streak window.
    km_by_day: dict[date, float] = {}
    for r in data:
        d = date.fromisoformat(r["start_date"])
        km_by_day[d] = km_by_day.get(d, 0.0) + (r["distance_km"] or 0.0)

    def streak_km(s: Streak) -> float:
        return round(sum(km for d, km in km_by_day.items() if s.start_date <= d <= s.end_date), 3)

    today = _today_local()
    streaks = compute_streaks(run_dates, today)

    current = next((s for s in streaks if s.is_current), None)
    longest = streaks[0] if streaks else None
    longest_length = longest.length_days if longest else 0

    top = [
        {
            "start_date": s.start_date.isoformat(),
            "end_date": s.end_date.isoformat(),
            "length_days": s.length_days,
            "is_current": s.is_current,
        }
        for s in streaks[:5]
    ]

    return {
        "current_streak": current.length_days if current else 0,
        "current_streak_km": streak_km(current) if current else 0.0,
        "longest_streak": longest_length,
        "longest_streak_km": streak_km(longest) if longest else 0.0,
        "top_streaks": top,
    }


def _today_local() -> date:
    """Match get_current_streak's America/New_York anchor so /streaks
    agrees with the legacy single-streak endpoint about what "today" is."""
    from datetime import datetime

    return datetime.now(ZoneInfo("America/New_York")).date()


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
    # 180 months = 15 yrs, covers the full streak's pace history (SB-184).
    limit: int = Query(12, ge=1, le=180),
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


@cached(ttl=60, key_prefix="stats:goals")
async def _goals(user_id: UUID) -> dict[str, Any]:
    supabase = get_supabase_client()
    token_repo = TokenRepository(supabase)
    goals_repo = GoalsRepository(supabase)
    runs_repo = RunsRepository(supabase)

    source_id = token_repo.get_source_id_for_user(user_id, "smashrun")
    return build_goals_block(user_id, source_id, goals_repo, _today_local(), runs_repo)


@router.get("/goals")
async def get_goals(
    user_id: UUID = Depends(authenticate_request),
) -> dict[str, Any]:
    """Current-year and current-month distance goals for the authenticated user.

    Reads from the ``goals`` table (populated on each sync). Either field is
    null when no goal is stored for that period or no SmashRun source is
    linked. Shape matches what the publish_status job emits to status.json,
    so the dashboard and the public qualityplaybook.dev tile share the same
    GoalProgress structure.
    """
    return await _goals(user_id)


@cached(ttl=60, key_prefix="stats:goals:history")
async def _goals_history(user_id: UUID) -> list[dict[str, Any]]:
    supabase = get_supabase_client()
    token_repo = TokenRepository(supabase)
    goals_repo = GoalsRepository(supabase)
    runs_repo = RunsRepository(supabase)

    source_id = token_repo.get_source_id_for_user(user_id, "smashrun")
    return build_goal_history(user_id, source_id, goals_repo, runs_repo)


@router.get("/goals/history")
async def get_goals_history(
    user_id: UUID = Depends(authenticate_request),
) -> list[dict[str, Any]]:
    """Full goal history — every past/current period with target vs achieved.

    One item per goal that has a target, newest period first. "Achieved" is
    recomputed from the user's runs (the ``monthly_summary`` view), so closed
    months are exact rather than frozen at the goals table's cached progress.
    Each item carries ``year``/``month``/``period``/``hit`` for grouping and
    hit/miss badging in the UI.
    """
    return await _goals_history(user_id)


@router.get("/splits")
def get_split_analysis(
    user_id: UUID = Depends(authenticate_request),
    since: date | None = Query(default=None, description="Only runs on/after this date"),
    until: date | None = Query(default=None, description="Only runs on/before this date"),
    limit: int = Query(default=30, ge=1, le=200, description="Most-recent N runs with splits"),
) -> dict[str, Any]:
    """Negative-split / per-mile pace analysis over recent runs that have splits.

    Returns a headline summary (negative-split rate, avg 1st vs last mile, fade)
    plus a per-run breakdown. Empty when no runs have splits yet (run
    ``stk splits backfill`` first).
    """
    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)
    runs = runs_repo.get_runs_with_splits(user_id, since=since, until=until, limit=limit)

    per_run: list[dict[str, Any]] = []
    for run in runs:
        rows = runs_repo.get_splits_for_run(UUID(run["id"]))
        analysis = analyze_run(rows)
        if analysis is None:
            continue
        per_run.append(
            {
                "run_id": run["id"],
                "date": run.get("start_date"),
                "distance_km": run.get("distance_km"),
                **{k: v for k, v in analysis.items() if k != "splits"},
            }
        )

    return {"summary": summarize(list(per_run)), "runs": per_run}
