"""SB-291: route leaderboard — repo grouping + endpoint wiring."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from backend.routes import runs as runs_module
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


# ---- endpoint wiring ----


class _EndpointRepo:
    def __init__(self, routes: list[dict[str, Any]]) -> None:
        self._routes = routes

    def __call__(self, _supabase: Any) -> _EndpointRepo:
        return self

    def get_route_leaderboard(self, user_id: Any, min_runs: int = 2) -> list[dict[str, Any]]:
        assert user_id == USER
        return self._routes


def test_endpoint_shapes_count_and_routes(monkeypatch: Any) -> None:
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", _EndpointRepo([{"run_count": 47}]))

    out = asyncio.run(runs_module.route_leaderboard(user_id=USER, min_runs=2))
    assert out == {"count": 1, "routes": [{"run_count": 47}]}
