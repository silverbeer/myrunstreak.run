"""SB-291: route leaderboard — repo grouping + endpoint wiring."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from backend.routes import runs as runs_module
from src.shared.geo import decode_polyline, encode_polyline
from src.shared.supabase_ops.runs_repository import RunsRepository

USER = uuid4()


class _FakeQuery:
    """Swallows the whole query chain; execute() returns the canned rows."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def __getattr__(self, _name: str) -> Any:
        return self

    def __call__(self, *_a: Any, **_k: Any) -> _FakeQuery:
        return self

    def execute(self) -> Any:
        return SimpleNamespace(data=self._rows)


def _repo(rows: list[dict[str, Any]]) -> RunsRepository:
    return RunsRepository(_FakeQuery(rows))  # type: ignore[arg-type]


def _run(lat: float, lon: float, km: float, pace: float, date: str) -> dict[str, Any]:
    return {
        "start_latitude": lat,
        "start_longitude": lon,
        "distance_km": km,
        "average_pace_min_per_km": pace,
        "start_date": date,
    }


def test_groups_same_start_and_distance_into_one_route() -> None:
    rows = [
        _run(42.2626, -71.8023, 4.0, 6.20, "2026-01-01"),
        _run(42.2626, -71.8023, 4.1, 5.90, "2026-02-01"),  # same cell + bucket
        _run(42.2626, -71.8023, 3.9, 6.00, "2026-03-01"),
        _run(41.8934, -87.6244, 5.0, 5.50, "2026-01-15"),  # different city
        _run(41.8934, -87.6244, 5.0, 5.60, "2026-02-15"),
        _run(40.0000, -75.0000, 3.0, 6.10, "2026-01-20"),  # only once -> excluded
    ]
    routes = _repo(rows).get_route_leaderboard(USER, min_runs=2)

    assert len(routes) == 2
    # Sorted by run count desc.
    assert routes[0]["run_count"] == 3
    assert routes[1]["run_count"] == 2
    top = routes[0]
    assert top["best_pace_min_per_km"] == 5.9  # fastest of the three
    assert top["avg_pace_min_per_km"] == round((6.20 + 5.90 + 6.00) / 3, 2)
    assert top["first_date"] == "2026-01-01"
    assert top["last_date"] == "2026-03-01"
    # pace_series is chronological (drives the sparkline).
    assert top["pace_series"] == [6.2, 5.9, 6.0]


def test_min_runs_filter() -> None:
    rows = [
        _run(42.26, -71.80, 4.0, 6.0, "2026-01-01"),
        _run(42.26, -71.80, 4.0, 6.0, "2026-02-01"),
    ]
    assert _repo(rows).get_route_leaderboard(USER, min_runs=3) == []
    assert len(_repo(rows).get_route_leaderboard(USER, min_runs=2)) == 1


def test_distance_separates_routes_from_same_start() -> None:
    # Same trailhead, two different loop lengths -> two routes.
    rows = [
        _run(42.26, -71.80, 4.0, 6.0, "2026-01-01"),
        _run(42.26, -71.80, 4.0, 6.0, "2026-02-01"),
        _run(42.26, -71.80, 8.0, 6.0, "2026-01-10"),
        _run(42.26, -71.80, 8.0, 6.0, "2026-02-10"),
    ]
    routes = _repo(rows).get_route_leaderboard(USER, min_runs=2)
    assert len(routes) == 2
    assert {round(r["distance_km"], 1) for r in routes} == {4.0, 8.0}


def test_get_route_for_run_returns_count_and_rank() -> None:
    # Two routes; the queried run belongs to the busier one.
    rows = [
        _run(42.244, -71.651, 4.0, 6.0, "2026-01-01"),
        _run(42.244, -71.650, 4.0, 5.9, "2026-02-01"),  # precision=2 folds these together
        _run(42.244, -71.651, 4.0, 6.1, "2026-03-01"),
        _run(41.893, -87.624, 5.0, 5.5, "2026-01-01"),
        _run(41.893, -87.624, 5.0, 5.6, "2026-02-01"),
    ]
    got = _repo(rows).get_route_for_run(USER, 42.2441, -71.6509, 4.05)
    assert got is not None
    assert got["run_count"] == 3  # all three home runs, split cells folded by precision=2
    assert got["rank"] == 1  # busiest route
    assert got["total_routes"] == 2
    assert got["best_pace_min_per_km"] == 5.9


def test_get_route_for_run_none_for_unseen_start() -> None:
    rows = [_run(42.244, -71.651, 4.0, 6.0, "2026-01-01")]
    assert _repo(rows).get_route_for_run(USER, 10.0, 10.0, 4.0) is None


# ---- shape-based grouping (SB-394) ----


class _FakeTables:
    """Fake client that answers per table, so runs and run_tracks can differ."""

    def __init__(self, runs: list[dict[str, Any]], tracks: list[dict[str, Any]]) -> None:
        self._by_table = {"runs": runs, "run_tracks": tracks}

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self._by_table[name])


def _shape_repo(runs: list[dict[str, Any]], tracks: list[dict[str, Any]]) -> RunsRepository:
    return RunsRepository(_FakeTables(runs, tracks))  # type: ignore[arg-type]


def _track_run(run_id: str, km: float, pace: float, date: str) -> dict[str, Any]:
    """A home-start run — same cell and distance bucket for every one of these."""
    return {"id": run_id, **_run(42.244, -71.651, km, pace, date)}


def _poly(dlat: float, dlon: float) -> str:
    """Encoded rectangular loop out of the home cell — the run's traced path."""
    lat, lon = 42.244, -71.651
    pts: list[tuple[float, float]] = []
    corners = [(0.0, 0.0), (dlat, 0.0), (dlat, dlon), (0.0, dlon), (0.0, 0.0)]
    for (a1, o1), (a2, o2) in zip(corners, corners[1:], strict=False):
        for i in range(9):
            t = i / 8
            pts.append((lat + a1 + (a2 - a1) * t, lon + o1 + (o2 - o1) * t))
    return encode_polyline(pts)


NORTH = _poly(0.006, 0.006)
SOUTH = _poly(-0.006, -0.006)


def test_shape_splits_one_coarse_group_into_real_routes() -> None:
    """Same house, same distance, different streets -> two routes, not one."""
    runs = [
        _track_run("r1", 5.5, 6.0, "2026-01-01"),
        _track_run("r2", 5.5, 5.8, "2026-02-01"),
        _track_run("r3", 5.5, 6.1, "2026-03-01"),
        _track_run("r4", 5.5, 5.9, "2026-04-01"),
    ]
    tracks = [
        {"run_id": "r1", "polyline": NORTH},
        {"run_id": "r2", "polyline": NORTH},
        {"run_id": "r3", "polyline": SOUTH},
        {"run_id": "r4", "polyline": SOUTH},
    ]
    repo = _shape_repo(runs, tracks)

    # Legacy grouping calls all four one route.
    assert len(repo.get_route_leaderboard(USER, min_runs=2)) == 1

    routes = repo.get_route_leaderboard(USER, min_runs=2, use_shape=True)
    assert len(routes) == 2
    assert [r["run_count"] for r in routes] == [2, 2]
    # Keys stay distinct even though the coarse (cell, distance) key is shared.
    assert routes[0]["route_key"] != routes[1]["route_key"]


def test_shape_variants_nest_and_sum_to_the_family() -> None:
    detour = encode_polyline([*decode_polyline(NORTH), (42.244, -71.6600), (42.244, -71.6650)])
    runs = [
        _track_run("r1", 5.5, 6.0, "2026-01-01"),
        _track_run("r2", 5.5, 5.8, "2026-02-01"),
        _track_run("r3", 5.5, 6.1, "2026-03-01"),
    ]
    tracks = [
        {"run_id": "r1", "polyline": NORTH},
        {"run_id": "r2", "polyline": NORTH},
        {"run_id": "r3", "polyline": detour},
    ]
    routes = _shape_repo(runs, tracks).get_route_leaderboard(USER, min_runs=2, use_shape=True)

    assert len(routes) == 1  # one family — the detour is a variation, not a new route
    family = routes[0]
    assert family["run_count"] == 3
    assert sum(v["run_count"] for v in family["variants"]) == family["run_count"]
    assert [v["run_count"] for v in family["variants"]] == [2, 1]  # biggest first


def test_shape_keeps_runs_that_have_no_polyline() -> None:
    """Backfill is incomplete; an untracked run must not vanish from the board."""
    runs = [
        _track_run("r1", 5.5, 6.0, "2026-01-01"),
        _track_run("r2", 5.5, 5.8, "2026-02-01"),
        _track_run("r3", 5.5, 6.1, "2026-03-01"),
    ]
    tracks = [{"run_id": "r1", "polyline": NORTH}, {"run_id": "r2", "polyline": NORTH}]
    routes = _shape_repo(runs, tracks).get_route_leaderboard(USER, min_runs=1, use_shape=True)

    assert sum(r["run_count"] for r in routes) == 3
    assert sorted(r["run_count"] for r in routes) == [1, 2]  # r3 stands alone


def test_get_route_for_run_by_id_returns_family_and_variant_counts() -> None:
    detour = encode_polyline([*decode_polyline(NORTH), (42.244, -71.6600), (42.244, -71.6650)])
    runs = [
        _track_run("r1", 5.5, 6.0, "2026-01-01"),
        _track_run("r2", 5.5, 5.8, "2026-02-01"),
        _track_run("r3", 5.5, 6.1, "2026-03-01"),
        _track_run("r4", 5.5, 6.2, "2026-04-01"),
    ]
    tracks = [
        {"run_id": "r1", "polyline": NORTH},
        {"run_id": "r2", "polyline": NORTH},
        {"run_id": "r3", "polyline": detour},
        {"run_id": "r4", "polyline": SOUTH},
    ]
    got = _shape_repo(runs, tracks).get_route_for_run(
        USER, 42.244, -71.651, 5.5, run_id="r3", use_shape=True
    )

    assert got is not None
    assert got["run_count"] == 3  # the family: two plain + the detour
    assert got["variant_run_count"] == 1  # this exact version, run once
    assert got["total_routes"] == 2  # the SOUTH loop is the other route


# ---- endpoint wiring ----


class _EndpointRepo:
    def __init__(self, routes: list[dict[str, Any]]) -> None:
        self._routes = routes

    def __call__(self, _supabase: Any) -> _EndpointRepo:
        return self

    def get_route_leaderboard(
        self, user_id: Any, min_runs: int = 2, use_shape: bool = False
    ) -> list[dict[str, Any]]:
        assert user_id == USER
        self.used_shape = use_shape
        return self._routes


def test_endpoint_shapes_count_and_routes(monkeypatch: Any) -> None:
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", _EndpointRepo([{"run_count": 47}]))

    out = asyncio.run(runs_module.route_leaderboard(user_id=USER, min_runs=2, shape=False))
    assert out == {"count": 1, "routes": [{"run_count": 47}]}


def test_endpoint_strips_run_ids_from_the_payload(monkeypatch: Any) -> None:
    """run_ids are an internal lookup aid — tens of KB of UUIDs on the wire."""
    repo = _EndpointRepo(
        [
            {
                "run_count": 3,
                "run_ids": ["a", "b", "c"],
                "variants": [{"run_count": 3, "run_ids": []}],
            }
        ]
    )
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", repo)

    out = asyncio.run(runs_module.route_leaderboard(user_id=USER, min_runs=2, shape=True))
    assert repo.used_shape is True
    assert "run_ids" not in out["routes"][0]
    assert "run_ids" not in out["routes"][0]["variants"][0]
