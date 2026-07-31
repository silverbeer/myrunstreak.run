"""Repository for runs/activities data operations in Supabase."""

import logging
from collections.abc import Callable
from datetime import date
from statistics import median
from typing import Any, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from src.shared.geo import decode_polyline
from src.shared.route_shape import MAX_CLUSTER_MEMBERS, families_and_variants, fingerprint
from supabase import Client

logger = logging.getLogger(__name__)


class RunsRepository:
    """
    Repository for running activity data operations.

    Handles all CRUD operations for runs, splits, and related data.
    """

    def __init__(self, supabase: Client):
        """
        Initialize repository with Supabase client.

        Args:
            supabase: Authenticated Supabase client
        """
        self.supabase = supabase

    def upsert_run(
        self, user_id: UUID, source_id: UUID, run_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Insert or update a run.

        Uses ON CONFLICT to handle duplicates based on (user_id, source_id, source_activity_id).

        Args:
            user_id: User UUID
            source_id: Source UUID (user_sources.id)
            run_data: Run data dictionary (mapped from Activity model)

        Returns:
            Inserted/updated run record

        Raises:
            Exception: If upsert fails
        """
        # Add user_id and source_id
        run_data["user_id"] = str(user_id)
        run_data["source_id"] = str(source_id)

        try:
            result = (
                self.supabase.table("runs")
                .upsert(run_data, on_conflict="user_id,source_id,source_activity_id")
                .execute()
            )

            logger.debug(f"Upserted run {run_data.get('source_activity_id')} for user {user_id}")
            data_list = cast(list[dict[str, Any]], result.data)

            return data_list[0]

        except Exception as e:
            logger.error(f"Failed to upsert run {run_data.get('source_activity_id')}: {e}")
            raise

    def get_run_by_id(self, run_id: UUID) -> dict[str, Any] | None:
        """
        Get a run by its UUID.

        Args:
            run_id: Run UUID

        Returns:
            Run record or None if not found
        """
        result = self.supabase.table("runs").select("*").eq("id", str(run_id)).execute()
        data_list = cast(list[dict[str, Any]], result.data)

        return data_list[0] if data_list else None

    def get_run_by_activity_id(self, user_id: UUID, activity_id: str) -> dict[str, Any] | None:
        """A user's run by its source activity id (what the frontend holds)."""
        result = (
            self.supabase.table("runs")
            .select("*")
            .eq("user_id", str(user_id))
            .eq("source_activity_id", activity_id)
            .limit(1)
            .execute()
        )
        data_list = cast(list[dict[str, Any]], result.data)
        return data_list[0] if data_list else None

    def get_track_polyline(self, run_id: UUID) -> dict[str, Any] | None:
        """A run's stored simplified polyline, or None if not backfilled (SB-309)."""
        result = (
            self.supabase.table("run_tracks")
            .select("polyline, point_count, encoded_precision")
            .eq("run_id", str(run_id))
            .limit(1)
            .execute()
        )
        data = cast(list[dict[str, Any]], result.data)
        return data[0] if data else None

    def upsert_track(
        self, run_id: UUID, polyline: str, point_count: int, precision: int = 5
    ) -> None:
        """Store/refresh a run's simplified encoded polyline (SB-309)."""
        self.supabase.table("run_tracks").upsert(
            {
                "run_id": str(run_id),
                "polyline": polyline,
                "point_count": point_count,
                "encoded_precision": precision,
            },
            on_conflict="run_id",
        ).execute()

    @staticmethod
    def _paginate(
        fetch_page: Callable[[int, int], list[dict[str, Any]]], page_size: int = 1000
    ) -> list[dict[str, Any]]:
        """Fetch every row across PostgREST's 1000-row response cap.

        Supabase caps a single response at ~1000 rows regardless of .limit(), so
        anything scanning a user's full history (thousands of runs) must page or
        it silently truncates. fetch_page(offset, size) runs one .range() query.
        """
        out: list[dict[str, Any]] = []
        offset = 0
        while True:
            batch = fetch_page(offset, page_size)
            out.extend(batch)
            if len(batch) < page_size:
                return out
            offset += page_size

    def get_all_track_polylines(self, user_id: UUID) -> list[dict[str, Any]]:
        """Every stored polyline for a user's runs — the territory-heatmap data
        source (SB-309). Joins run_tracks to runs so it's user-scoped. Paged so
        it returns all of a multi-thousand-run history, not just the first 1000."""

        def page(off: int, size: int) -> list[dict[str, Any]]:
            return cast(
                list[dict[str, Any]],
                self.supabase.table("run_tracks")
                .select("polyline, encoded_precision, runs!inner(user_id)")
                .eq("runs.user_id", str(user_id))
                .range(off, off + size - 1)
                .execute()
                .data,
            )

        rows = self._paginate(page)
        return [
            {"polyline": r["polyline"], "encoded_precision": r["encoded_precision"]} for r in rows
        ]

    def get_polylines_by_run_id(self, user_id: UUID) -> dict[str, str]:
        """``{run_id: polyline}`` for every stored track (SB-394 shape grouping).

        Same rows as :meth:`get_all_track_polylines`, keyed so the leaderboard
        can attach a track to the run it belongs to.
        """

        def page(off: int, size: int) -> list[dict[str, Any]]:
            return cast(
                list[dict[str, Any]],
                self.supabase.table("run_tracks")
                .select("run_id, polyline, runs!inner(user_id)")
                .eq("runs.user_id", str(user_id))
                .range(off, off + size - 1)
                .execute()
                .data,
            )

        return {r["run_id"]: r["polyline"] for r in self._paginate(page) if r.get("polyline")}

    def get_runs_for_verify(
        self, user_id: UUID, date_from: date, date_to: date
    ) -> list[dict[str, Any]]:
        """Runs in a date range, keyed for reconciliation against the source (SB-477).

        Only the fields the diff compares, so a wide window stays cheap. Paged,
        because a multi-year window exceeds PostgREST's 1000-row cap and would
        otherwise truncate silently — reporting phantom "missing from STK" rows
        for everything past the first page.
        """

        def page(off: int, size: int) -> list[dict[str, Any]]:
            return cast(
                list[dict[str, Any]],
                self.supabase.table("runs")
                .select("id, source_activity_id, start_date, distance_km, duration_seconds")
                .eq("user_id", str(user_id))
                .gte("start_date", date_from.isoformat())
                .lte("start_date", date_to.isoformat())
                .order("start_date")
                .range(off, off + size - 1)
                .execute()
                .data,
            )

        return self._paginate(page)

    def count_tracks(self, user_id: UUID) -> int:
        """How many of a user's runs have a stored polyline (backfill progress)."""
        result = (
            self.supabase.table("run_tracks")
            .select("run_id, runs!inner(user_id)", count="exact")
            .eq("runs.user_id", str(user_id))
            .execute()
        )
        return cast(int, result.count or 0)

    def set_run_audio(
        self,
        user_id: UUID,
        activity_id: str,
        audio_type: str | None,
        audio_note: str | None,
    ) -> dict[str, Any] | None:
        """Set a run's audio log (what was playing) — SB-302. User-scoped so a
        caller can only annotate their own run. Returns the updated row, or None
        if no run matched (not found / not owned)."""
        result = (
            self.supabase.table("runs")
            .update({"audio_type": audio_type, "audio_note": audio_note})
            .eq("user_id", str(user_id))
            .eq("source_activity_id", activity_id)
            .execute()
        )
        data = cast(list[dict[str, Any]], result.data)
        return data[0] if data else None

    def _apply_run_filters(
        self,
        query: Any,
        date_from: date | None,
        date_to: date | None,
        distance_min: float | None,
        distance_max: float | None,
        weather_type: str | None = None,
        temp_min: float | None = None,
        temp_max: float | None = None,
        pace_min: float | None = None,
        pace_max: float | None = None,
        on_this_day: str | None = None,
        hour_min: int | None = None,
        hour_max: int | None = None,
    ) -> Any:
        """Apply optional filters to a runs query (SB-184 date/distance;
        SB-269 weather/temp/pace + on-this-day)."""
        if date_from is not None:
            query = query.gte("start_date", date_from.isoformat())
        if date_to is not None:
            query = query.lte("start_date", date_to.isoformat())
        if distance_min is not None:
            query = query.gte("distance_km", distance_min)
        if distance_max is not None:
            query = query.lte("distance_km", distance_max)
        if weather_type is not None:
            query = query.eq("weather_type", weather_type)
        if temp_min is not None:
            query = query.gte("temperature_celsius", temp_min)
        if temp_max is not None:
            query = query.lte("temperature_celsius", temp_max)
        if pace_min is not None:
            query = query.gte("average_pace_min_per_km", pace_min)
        if pace_max is not None:
            query = query.lte("average_pace_min_per_km", pace_max)
        if hour_min is not None:
            query = query.gte("start_hour", hour_min)
        if hour_max is not None:
            query = query.lte("start_hour", hour_max)
        if on_this_day is not None:
            # "MM-DD" across every plausible streak year -> exact date list, so
            # count + pagination keep working (no post-filtering).
            month, day = on_this_day.split("-")
            dates = []
            for year in range(2000, date.today().year + 1):
                try:
                    dates.append(date(year, int(month), int(day)).isoformat())
                except ValueError:  # Feb 29 in non-leap years
                    continue
            query = query.in_("start_date", dates)
        return query

    def get_runs_by_user(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        distance_min: float | None = None,
        distance_max: float | None = None,
        sort_by: str = "start_date_time_local",
        sort_desc: bool = True,
        **extra_filters: Any,
    ) -> list[dict[str, Any]]:
        """
        Get runs for a specific user with pagination + optional filters.

        Args:
            user_id: User UUID
            limit: Maximum number of runs to return
            offset: Number of runs to skip
            date_from: Only runs on/after this date (inclusive)
            date_to: Only runs on/before this date (inclusive)
            distance_min: Only runs >= this distance in km
            distance_max: Only runs <= this distance in km

        Returns:
            List of run records
        """
        query = self.supabase.table("runs").select("*").eq("user_id", str(user_id))
        query = self._apply_run_filters(
            query, date_from, date_to, distance_min, distance_max, **extra_filters
        )
        # Sortable columns are whitelisted at the route; date is the tiebreaker.
        result = (
            query.order(sort_by, desc=sort_desc, nullsfirst=False)
            .order("start_date_time_local", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return cast(list[dict[str, Any]], result.data)

    def count_runs_by_user(
        self,
        user_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        distance_min: float | None = None,
        distance_max: float | None = None,
        **extra_filters: Any,
    ) -> int:
        """Count runs for a user, honoring the same filters as get_runs_by_user."""
        query = self.supabase.table("runs").select("id", count="exact").eq("user_id", str(user_id))
        query = self._apply_run_filters(
            query, date_from, date_to, distance_min, distance_max, **extra_filters
        )
        result = query.execute()
        return cast(int, result.count or 0)

    def get_runs_head(self, user_id: UUID) -> dict[str, Any]:
        """Cheap change-signal for a user's run history: total count and the
        latest run's local date.

        Used by ``GET /runs/head`` to build a version token
        (``"{count}:{latest_run_date}"``) that clients use to gate their local
        cache — it advances only when a run is added or removed, so re-syncs
        that merely re-upsert existing runs (bumping ``updated_at``) do not
        needlessly bust the cache. In-place edits to an existing run are
        intentionally NOT reflected (rare; clients can force a refresh).
        """
        count = self.count_runs_by_user(user_id)
        result = (
            self.supabase.table("runs")
            .select("start_date_time_local")
            .eq("user_id", str(user_id))
            .order("start_date_time_local", desc=True)
            .limit(1)
            .execute()
        )
        rows = cast(list[dict[str, Any]], result.data)
        latest = rows[0]["start_date_time_local"] if rows else None
        return {"count": count, "latest_run_date": latest}

    def summarize_runs(self, user_id: UUID, **filters: Any) -> dict[str, Any]:
        """Aggregate the FULL filtered set (SB-269 conditions impact): count,
        total km, and distance-weighted avg pace. Fetches only two columns."""

        def page(off: int, size: int) -> list[dict[str, Any]]:
            query = (
                self.supabase.table("runs")
                .select("distance_km,average_pace_min_per_km")
                .eq("user_id", str(user_id))
            )
            query = self._apply_run_filters(
                query,
                filters.get("date_from"),
                filters.get("date_to"),
                filters.get("distance_min"),
                filters.get("distance_max"),
                **{
                    k: v
                    for k, v in filters.items()
                    if k not in ("date_from", "date_to", "distance_min", "distance_max")
                },
            )
            return cast(
                list[dict[str, Any]],
                query.order("start_date", desc=False)  # stable paging needs a total order
                .range(off, off + size - 1)
                .execute()
                .data,
            )

        rows = self._paginate(page)
        total_km = 0.0
        weighted = 0.0
        paced_km = 0.0
        for r in rows:
            km = float(r["distance_km"] or 0)
            total_km += km
            pace = r.get("average_pace_min_per_km")
            if pace is not None and km > 0:
                weighted += float(pace) * km
                paced_km += km
        return {
            "count": len(rows),
            "total_km": round(total_km, 2),
            "avg_pace_min_per_km": round(weighted / paced_km, 4) if paced_km else None,
        }

    def get_runs_by_date_range(
        self, user_id: UUID, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """
        Get runs within a date range for a user.

        Args:
            user_id: User UUID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of run records
        """
        result = (
            self.supabase.table("runs")
            .select("*")
            .eq("user_id", str(user_id))
            .gte("start_date", start_date.isoformat())
            .lte("start_date", end_date.isoformat())
            .order("start_date_time_local", desc=True)
            .limit(10000)  # Override PostgREST default of 1000
            .execute()
        )

        return cast(list[dict[str, Any]], result.data)

    def get_user_overall_stats(self, user_id: UUID) -> dict[str, Any]:
        """
        Get overall running statistics for a user.

        Uses database-level aggregation via RPC to avoid PostgREST row limits.

        Args:
            user_id: User UUID

        Returns:
            Dict with total_runs, total_km, avg_km, longest_run_km, avg_pace
        """
        try:
            # Use database function for server-side aggregation
            result = self.supabase.rpc("get_user_stats", {"p_user_id": str(user_id)}).execute()

            if result.data:
                stats = result.data
                # Handle both direct dict and list responses
                if isinstance(stats, list) and len(stats) > 0:
                    stats = stats[0]
                stats_dict = cast(dict[str, Any], stats)
                return {
                    "total_runs": int(stats_dict.get("total_runs", 0)),
                    "total_km": float(stats_dict.get("total_km", 0)),
                    "avg_km": float(stats_dict.get("avg_km", 0)),
                    "longest_run_km": float(stats_dict.get("longest_run_km", 0)),
                    "avg_pace_min_per_km": float(stats_dict.get("avg_pace_min_per_km", 0)),
                }
        except Exception as e:
            logger.warning(f"RPC get_user_stats failed, falling back to client-side: {e}")

        # Fallback to client-side aggregation (limited to 1000 rows)
        fallback_result = (
            self.supabase.table("runs")
            .select("distance_km, average_pace_min_per_km")
            .eq("user_id", str(user_id))
            .limit(10000)
            .execute()
        )

        runs = cast(list[dict[str, Any]], fallback_result.data)

        if not runs or len(runs) == 0:
            return {
                "total_runs": 0,
                "total_km": 0,
                "avg_km": 0,
                "longest_run_km": 0,
                "avg_pace_min_per_km": 0,
            }

        total_runs = len(runs)
        distances = [float(r["distance_km"]) for r in runs]
        paces = [
            float(r["average_pace_min_per_km"])
            for r in runs
            if r["average_pace_min_per_km"] is not None
        ]

        return {
            "total_runs": total_runs,
            "total_km": round(sum(distances), 2),
            "avg_km": round(sum(distances) / total_runs, 2) if total_runs > 0 else 0,
            "longest_run_km": round(max(distances), 2) if distances else 0,
            "avg_pace_min_per_km": round(sum(paces) / len(paces), 2) if paces else 0,
        }

    @staticmethod
    def _summarize_route(
        members: list[dict[str, Any]], route_key: str, lat: float, lon: float, bucket: float
    ) -> dict[str, Any]:
        """One leaderboard row from the runs that belong to it."""
        chron = sorted(members, key=lambda m: m["start_date"])
        paces = [
            float(m["average_pace_min_per_km"])
            for m in chron
            if m["average_pace_min_per_km"] is not None
        ]
        return {
            "route_key": route_key,
            "start_latitude": lat,
            "start_longitude": lon,
            "distance_km": bucket,
            "run_count": len(members),
            "first_date": chron[0]["start_date"],
            "last_date": chron[-1]["start_date"],
            "best_pace_min_per_km": round(min(paces), 2) if paces else None,
            "avg_pace_min_per_km": round(sum(paces) / len(paces), 2) if paces else None,
            "pace_series": [round(p, 2) for p in paces],
        }

    def get_route_leaderboard(
        self,
        user_id: UUID,
        min_runs: int = 2,
        precision: int = 2,
        dist_bucket_km: float = 0.5,
        use_shape: bool = False,
    ) -> list[dict[str, Any]]:
        """Group a user's GPS runs into repeated routes (SB-291).

        A route is approximated by (rounded start cell, distance bucket) — for
        loop runs (start ≈ end, the common case) that identifies the route well
        without any polyline. Treadmill / no-GPS runs are excluded (they have
        no start coordinates).

        precision=2 (~1.1 km cell) instead of 3: at 3 decimals the same physical
        route split across a rounding boundary into two rows (SB-289 — e.g. one
        home route counted as 20 + 18). A home-based runner starts most routes
        from one spot, so the distance bucket does the real separating; the
        coarser cell folds the boundary jitter back together.

        ``use_shape=True`` (SB-394) subdivides each coarse group by the actual
        path the runs traced, which is the only thing that separates two routes
        leaving the same house at the same distance. Each returned row is then a
        route *family* (slight variations counted together) carrying a
        ``variants`` list. Off by default until the SB-310 polyline backfill
        finishes — with partial coverage the split would be arbitrary.

        Args:
            user_id: User UUID
            min_runs: Only return routes run at least this many times
            precision: Decimal places to round start lat/lon (2 ≈ 1.1 km cell)
            dist_bucket_km: Distance bucket width in km
            use_shape: Subdivide groups by track shape (needs stored polylines)

        Returns:
            Routes sorted by run count desc. Each: route_key, start_latitude,
            start_longitude, distance_km (bucket midpoint), run_count,
            first_date, last_date, best_pace_min_per_km, avg_pace_min_per_km,
            pace_series (chronological avg pace per run, for a sparkline), and
            with use_shape also variants (the same shape, one level down).
        """

        def page(off: int, size: int) -> list[dict[str, Any]]:
            return cast(
                list[dict[str, Any]],
                self.supabase.table("runs")
                .select(
                    "id, start_latitude, start_longitude, distance_km, "
                    "average_pace_min_per_km, start_date"
                )
                .eq("user_id", str(user_id))
                .not_.is_("start_latitude", "null")
                .not_.is_("start_longitude", "null")
                .order("start_date", desc=False)  # stable paging needs a total order
                .range(off, off + size - 1)
                .execute()
                .data,
            )

        rows = self._paginate(page)

        groups: dict[tuple[float, float, float], list[dict[str, Any]]] = {}
        for r in rows:
            lat = round(float(r["start_latitude"]), precision)
            lon = round(float(r["start_longitude"]), precision)
            bucket = round(float(r["distance_km"]) / dist_bucket_km) * dist_bucket_km
            groups.setdefault((lat, lon, round(bucket, 3)), []).append(r)

        polylines = self.get_polylines_by_run_id(user_id) if use_shape else {}

        routes: list[dict[str, Any]] = []
        for (lat, lon, bucket), members in groups.items():
            for route in self._split_group(members, lat, lon, bucket, polylines, use_shape):
                if route["run_count"] >= min_runs:
                    routes.append(route)

        routes.sort(key=lambda x: x["run_count"], reverse=True)
        return routes

    def _split_group(
        self,
        members: list[dict[str, Any]],
        lat: float,
        lon: float,
        bucket: float,
        polylines: dict[str, str],
        use_shape: bool,
    ) -> list[dict[str, Any]]:
        """One coarse (cell, distance) group -> the route rows it really holds.

        Without shape data that's the single legacy row. With it, one row per
        family, each carrying its variants. The route_key is suffixed with the
        family's earliest run id so it stays stable as long as that run keeps
        anchoring the family — the row's position in the list is not stable and
        must never be used as an identity.
        """
        base_key = f"{lat},{lon},{bucket}"
        if not use_shape or len(members) > MAX_CLUSTER_MEMBERS:
            return [self._summarize_route(members, base_key, lat, lon, bucket)]

        fingerprints = [
            fingerprint(decode_polyline(polylines[m["id"]]))
            if m["id"] in polylines
            else frozenset()
            for m in members
        ]
        out: list[dict[str, Any]] = []
        for family in families_and_variants(fingerprints):
            flat = [members[i] for variant in family for i in variant]
            anchor = min(m["id"] for m in flat)
            route = self._summarize_route(flat, f"{base_key}#{anchor}", lat, lon, bucket)
            route["run_ids"] = [m["id"] for m in flat]
            route["variants"] = [
                self._summarize_route(
                    [members[i] for i in variant],
                    f"{base_key}#{min(members[i]['id'] for i in variant)}",
                    lat,
                    lon,
                    bucket,
                )
                for variant in sorted(family, key=len, reverse=True)
            ]
            for variant, summary in zip(
                sorted(family, key=len, reverse=True), route["variants"], strict=True
            ):
                summary["run_ids"] = [members[i]["id"] for i in variant]
            out.append(route)
        return out

    def get_route_for_run(
        self,
        user_id: UUID,
        start_latitude: float,
        start_longitude: float,
        distance_km: float,
        precision: int = 2,
        dist_bucket_km: float = 0.5,
        run_id: str | None = None,
        use_shape: bool = False,
    ) -> dict[str, Any] | None:
        """The route a given run belongs to, with its count + rank (SB-297).

        Reuses the leaderboard grouping so the route-card can show "run N times,
        #k of M" for a single activity. Returns None if the run has no GPS start
        (nothing to group on).

        With ``use_shape`` the row is a route family, so the run is located by
        id rather than by coordinates — several families share one (cell,
        distance) key and only membership says which one this run traced. Adds
        ``variant_run_count`` (how many times this exact version was run) beside
        the family's ``run_count``. Falls back to the coordinate match when no
        ``run_id`` is given.
        """
        board = self.get_route_leaderboard(
            user_id,
            min_runs=1,
            precision=precision,
            dist_bucket_km=dist_bucket_km,
            use_shape=use_shape,
        )
        lat = round(float(start_latitude), precision)
        lon = round(float(start_longitude), precision)
        bucket = round(round(float(distance_km) / dist_bucket_km) * dist_bucket_km, 3)
        key = f"{lat},{lon},{bucket}"

        for rank, route in enumerate(board, start=1):
            if run_id is not None and use_shape:
                if run_id not in route.get("run_ids", ()):
                    continue
            elif route["route_key"] != key:
                continue
            found = {
                "run_count": route["run_count"],
                "rank": rank,
                "total_routes": len(board),
                "best_pace_min_per_km": route["best_pace_min_per_km"],
            }
            for variant in route.get("variants", ()):
                if run_id is not None and run_id in variant.get("run_ids", ()):
                    found["variant_run_count"] = variant["run_count"]
                    found["variant_best_pace_min_per_km"] = variant["best_pace_min_per_km"]
                    break
            return found
        return None

    def get_conditions_penalty(
        self,
        user_id: UUID,
        temp_c: float = 24.0,
        humidity_pct: float = 70.0,
        min_steamy: int = 5,
    ) -> dict[str, Any] | None:
        """How much slower the user runs in hot + humid conditions (SB-304).

        Compares median pace on "steamy" runs (temp ≥ temp_c AND humidity ≥
        humidity_pct — the SB-269 flag's zone) against every other run. The
        spike found this is the only condition that meaningfully moves this
        runner's pace, so it's reported per-user rather than modeled.

        Returns the penalty in seconds/mile plus the run counts, or None if
        there aren't enough steamy runs to be meaningful.
        """

        def page(off: int, size: int) -> list[dict[str, Any]]:
            return cast(
                list[dict[str, Any]],
                self.supabase.table("runs")
                .select("average_pace_min_per_km, temperature_celsius, humidity_percent")
                .eq("user_id", str(user_id))
                .not_.is_("average_pace_min_per_km", "null")
                .order("start_date", desc=False)  # stable paging needs a total order
                .range(off, off + size - 1)
                .execute()
                .data,
            )

        rows = self._paginate(page)

        steamy: list[float] = []
        baseline: list[float] = []
        for r in rows:
            pace = r.get("average_pace_min_per_km")
            if pace is None:
                continue
            pace = float(pace)
            temp = r.get("temperature_celsius")
            humidity = r.get("humidity_percent")
            is_steamy = (
                temp is not None
                and humidity is not None
                and float(temp) >= temp_c
                and float(humidity) >= humidity_pct
            )
            (steamy if is_steamy else baseline).append(pace)

        if len(steamy) < min_steamy or not baseline:
            return None

        steamy_med = median(steamy)
        baseline_med = median(baseline)
        penalty_min_per_km = steamy_med - baseline_med
        return {
            "steamy_run_count": len(steamy),
            "baseline_run_count": len(baseline),
            "penalty_sec_per_mi": round(penalty_min_per_km * 1.609344 * 60),
            "steamy_median_pace_min_per_km": round(steamy_med, 3),
            "baseline_median_pace_min_per_km": round(baseline_med, 3),
            "temp_c": temp_c,
            "humidity_pct": humidity_pct,
        }

    def get_monthly_stats(self, user_id: UUID, limit: int = 12) -> list[dict[str, Any]]:
        """
        Get monthly statistics for a user using the monthly_summary view.

        Args:
            user_id: User UUID
            limit: Number of months to return

        Returns:
            List of monthly summary records
        """
        result = (
            self.supabase.table("monthly_summary")
            .select("*")
            .eq("user_id", str(user_id))
            .order("start_year", desc=True)
            .order("start_month", desc=True)
            .limit(limit)
            .execute()
        )

        return cast(list[dict[str, Any]], result.data)

    def get_current_streak(self, user_id: UUID) -> int:
        """
        Get the user's current running streak (consecutive days).

        Uses database function to avoid row limits and ensure accurate count.

        Args:
            user_id: User UUID

        Returns:
            Number of consecutive days with runs (0 if no current streak)
        """
        try:
            # Use database function for accurate streak calculation
            rpc_result = self.supabase.rpc(
                "get_current_streak", {"p_user_id": str(user_id)}
            ).execute()

            if rpc_result.data is not None:
                return int(cast(int, rpc_result.data))
        except Exception as e:
            logger.warning(f"RPC get_current_streak failed, falling back: {e}")

        # Fallback to client-side calculation (limited to 1000 rows)
        fallback_result = (
            self.supabase.table("runs")
            .select("start_date")
            .eq("user_id", str(user_id))
            .order("start_date", desc=True)
            .limit(10000)
            .execute()
        )

        data_list = cast(list[dict[str, Any]], fallback_result.data)

        if not data_list:
            return 0

        run_dates = {date.fromisoformat(row["start_date"]) for row in data_list}
        from datetime import datetime

        current_date = datetime.now(ZoneInfo("America/New_York")).date()
        streak = 0

        if current_date not in run_dates:
            current_date = date.fromordinal(current_date.toordinal() - 1)
            if current_date not in run_dates:
                return 0

        while current_date in run_dates:
            streak += 1
            current_date = date.fromordinal(current_date.toordinal() - 1)

        return streak

    def upsert_split(self, run_id: UUID, split_data: dict[str, Any]) -> dict[str, Any]:
        """
        Insert or update a split for a run.

        Args:
            run_id: Run UUID
            split_data: Split data dictionary

        Returns:
            Inserted/updated split record
        """
        split_data["run_id"] = str(run_id)

        result = (
            self.supabase.table("splits")
            .upsert(split_data, on_conflict="run_id,split_unit,split_number")
            .execute()
        )
        data_list = cast(list[dict[str, Any]], result.data)

        return data_list[0]

    def get_splits_for_run(self, run_id: UUID) -> list[dict[str, Any]]:
        """
        Get all splits for a run.

        Args:
            run_id: Run UUID

        Returns:
            List of split records
        """
        result = (
            self.supabase.table("splits")
            .select("*")
            .eq("run_id", str(run_id))
            .order("split_number")
            .execute()
        )

        return cast(list[dict[str, Any]], result.data)

    def get_runs_with_splits(
        self,
        user_id: UUID,
        since: date | None = None,
        until: date | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Runs that have stored splits (has_splits = TRUE), newest first."""
        query = (
            self.supabase.table("runs")
            .select("id, start_date, distance_km")
            .eq("user_id", str(user_id))
            .eq("has_splits", True)
        )
        if since is not None:
            query = query.gte("start_date", since.isoformat())
        if until is not None:
            query = query.lte("start_date", until.isoformat())
        result = query.order("start_date", desc=True).limit(limit).execute()
        return cast(list[dict[str, Any]], result.data)

    def set_has_splits(self, run_id: UUID, value: bool = True) -> None:
        """Flag a run as having (or not having) stored splits."""
        self.supabase.table("runs").update({"has_splits": value}).eq("id", str(run_id)).execute()

    def get_runs_missing_tracks(self, user_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
        """GPS runs with no stored polyline yet (SB-310 backfill), oldest first.

        Store-on-read covers viewed runs; this finds the rest. Diffs the GPS-run
        set against the stored-track set client-side (both are small — a few
        thousand ids — and PostgREST has no clean anti-join). Returns id +
        source_activity_id for a bounded batch.
        """

        def gps_page(off: int, size: int) -> list[dict[str, Any]]:
            return cast(
                list[dict[str, Any]],
                self.supabase.table("runs")
                .select("id, source_activity_id, start_date")
                .eq("user_id", str(user_id))
                .eq("has_gps_data", True)
                .not_.is_("start_latitude", "null")
                .order("start_date", desc=False)  # oldest first — fill history from the start
                .range(off, off + size - 1)
                .execute()
                .data,
            )

        def tracks_page(off: int, size: int) -> list[dict[str, Any]]:
            return cast(
                list[dict[str, Any]],
                self.supabase.table("run_tracks")
                .select("run_id, runs!inner(user_id)")
                .eq("runs.user_id", str(user_id))
                .range(off, off + size - 1)
                .execute()
                .data,
            )

        gps_runs = self._paginate(gps_page)
        have_ids = {r["run_id"] for r in self._paginate(tracks_page)}

        pending = [r for r in gps_runs if r["id"] not in have_ids]
        return pending[:limit]

    def count_runs_missing_tracks(self, user_id: UUID) -> int:
        """How many GPS runs still lack a stored polyline (backfill progress)."""
        return len(self.get_runs_missing_tracks(user_id, limit=10000))

    def get_runs_missing_splits(
        self,
        user_id: UUID,
        since: date | None = None,
        until: date | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Runs that have no stored splits yet (has_splits = FALSE), newest first.

        Returns just the fields a splits backfill needs: id + source_activity_id.
        """
        query = (
            self.supabase.table("runs")
            .select("id, source_activity_id, start_date")
            .eq("user_id", str(user_id))
            .eq("has_splits", False)
        )
        if since is not None:
            query = query.gte("start_date", since.isoformat())
        if until is not None:
            query = query.lte("start_date", until.isoformat())
        result = query.order("start_date", desc=True).limit(limit).execute()
        return cast(list[dict[str, Any]], result.data)

    def count_runs_missing_splits(self, user_id: UUID) -> int:
        """How many of a user's runs still have no stored splits (SB-184)."""
        result = (
            self.supabase.table("runs")
            .select("id", count="exact")
            .eq("user_id", str(user_id))
            .eq("has_splits", False)
            .execute()
        )
        return cast(int, result.count or 0)

    def delete_run(self, run_id: UUID) -> None:
        """
        Delete a run and all related data (cascades to splits, laps, etc.).

        Args:
            run_id: Run UUID
        """
        self.supabase.table("runs").delete().eq("id", str(run_id)).execute()
        logger.info(f"Deleted run {run_id}")

    def recalculate_user_stats(
        self, user_id: UUID, timezone: str = "America/New_York"
    ) -> dict[str, Any]:
        """
        Recalculate and store all running statistics for a user.

        Calls the database function to aggregate stats and store them in
        user_running_stats table. This avoids row limits for users with
        large datasets (e.g., multi-year streaks).

        Args:
            user_id: User UUID
            timezone: IANA timezone for accurate date boundaries (default: America/New_York)

        Returns:
            Dict with calculated statistics

        Raises:
            Exception: If recalculation fails
        """
        try:
            result = self.supabase.rpc(
                "recalculate_user_stats",
                {"p_user_id": str(user_id), "p_timezone": timezone},
            ).execute()

            if result.data:
                stats = result.data
                # Handle both direct dict and list responses
                if isinstance(stats, list) and len(stats) > 0:
                    stats = stats[0]
                stats_dict = cast(dict[str, Any], stats)
                logger.info(
                    f"Recalculated stats for user {user_id}: "
                    f"{stats_dict.get('lifetime_runs')} runs, "
                    f"{stats_dict.get('current_streak_days')} day streak"
                )
                return stats_dict

            return {}

        except Exception as e:
            logger.error(f"Failed to recalculate stats for user {user_id}: {e}")
            raise

    def get_user_running_stats(self, user_id: UUID) -> dict[str, Any] | None:
        """
        Get pre-calculated running statistics for a user.

        Fetches from the user_running_stats aggregation table. If no stats
        exist yet, returns None (caller should trigger recalculation).

        Args:
            user_id: User UUID

        Returns:
            Dict with all pre-calculated stats, or None if not found
        """
        result = (
            self.supabase.table("user_running_stats")
            .select("*")
            .eq("user_id", str(user_id))
            .execute()
        )

        data_list = cast(list[dict[str, Any]], result.data)
        return data_list[0] if data_list else None
