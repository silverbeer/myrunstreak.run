"""SB-622: an imported run's map comes from our stored polyline, not SmashRun."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from backend.routes import runs as runs_module
from fastapi import HTTPException
from src.shared.geo import encode_polyline

USER = uuid4()
RUN_ID = uuid4()
SOURCE_ID = uuid4()

# A short L-shaped route, ~100 m a side.
POINTS = [(42.2400, -71.6500), (42.2409, -71.6500), (42.2409, -71.6488)]

_RUN = {
    "id": str(RUN_ID),
    "source_id": str(SOURCE_ID),
    "start_date_time_local": "2026-08-08T10:50:35-04:00",
    "distance_km": "3.24",
    "duration_seconds": "1119",
    "average_pace_min_per_km": "5.75",
    "weather_type": None,
    "temperature_celsius": None,
}


class _Repo:
    def __init__(self, run: dict[str, Any] | None, polyline: str | None) -> None:
        self._run = run
        self._polyline = polyline
        self.upserted_tracks: list[Any] = []

    def __call__(self, _sb: Any) -> _Repo:
        return self

    def get_run_by_activity_id(self, _uid: Any, _aid: str) -> dict[str, Any] | None:
        return self._run

    def get_track_polyline(self, _run_id: Any) -> dict[str, Any] | None:
        return {"polyline": self._polyline} if self._polyline else None

    def get_route_for_run(self, *_a: Any, **_k: Any) -> dict[str, Any] | None:
        return None

    def upsert_track(self, *a: Any) -> None:
        self.upserted_tracks.append(a)


class _Users:
    def __init__(self, source_type: str) -> None:
        self._source_type = source_type

    def __call__(self, _sb: Any) -> _Users:
        return self

    def get_source_by_id(self, _sid: Any) -> dict[str, Any]:
        return {"source_type": self._source_type}


def _boom(*_a: Any, **_k: Any) -> Any:
    raise AssertionError("SmashRun must not be called for an imported run")


def _track(
    monkeypatch: Any,
    *,
    missing: bool = False,
    polyline: str | None = None,
    source_type: str = "import",
) -> Any:
    repo = _Repo(None if missing else _RUN, polyline)
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", repo)
    monkeypatch.setattr(runs_module, "UsersRepository", _Users(source_type))
    monkeypatch.setattr(runs_module, "_resolve_access_token", _boom)
    monkeypatch.setattr(runs_module, "SmashRunAPIClient", _boom)
    return asyncio.run(runs_module._track(USER, "gpx-abc123"))


def test_imported_run_track_comes_from_the_stored_polyline(monkeypatch: Any) -> None:
    out = _track(monkeypatch, polyline=encode_polyline(POINTS))

    assert out["has_track"] is True
    assert len(out["lat"]) == 3
    assert out["lat"][0] == pytest.approx(42.2400, abs=1e-4)
    assert out["lon"][2] == pytest.approx(-71.6488, abs=1e-4)


def test_imported_run_never_calls_smashrun(monkeypatch: Any) -> None:
    # _resolve_access_token and SmashRunAPIClient both raise if touched. The
    # owner may have no SmashRun connection at all, which is what used to make
    # this 500 before the track lookup even happened.
    _track(monkeypatch, polyline=encode_polyline(POINTS))


def test_distance_series_is_rederived_and_aligned(monkeypatch: Any) -> None:
    out = _track(monkeypatch, polyline=encode_polyline(POINTS))

    assert len(out["dist_km"]) == len(out["lat"])
    assert out["dist_km"][0] == 0.0
    assert out["dist_km"] == sorted(out["dist_km"])  # cumulative, never decreasing
    assert out["dist_km"][-1] == pytest.approx(0.2, abs=0.05)  # ~100 m + ~100 m


def test_per_point_series_are_empty_for_an_import(monkeypatch: Any) -> None:
    # run_tracks holds geometry only; the map draws an uncoloured line.
    out = _track(monkeypatch, polyline=encode_polyline(POINTS))

    assert out["pace_min_per_km"] == []
    assert out["heart_rate"] == []
    assert out["elevation_m"] == []


def test_imported_run_without_a_stored_track_reports_no_track(monkeypatch: Any) -> None:
    out = _track(monkeypatch, polyline=None)

    assert out["has_track"] is False
    assert out["lat"] == []
    # Still answers with the run's own stats rather than erroring.
    assert out["distance_km"] == 3.24


def test_degenerate_polyline_is_not_drawable(monkeypatch: Any) -> None:
    out = _track(monkeypatch, polyline=encode_polyline([(42.24, -71.65)]))

    assert out["has_track"] is False


def test_missing_run_is_404(monkeypatch: Any) -> None:
    with pytest.raises(HTTPException) as err:
        _track(monkeypatch, missing=True)
    assert err.value.status_code == 404


def test_synced_run_still_uses_the_smashrun_path(monkeypatch: Any) -> None:
    # The stub raises, proving the synced branch is the one taken — the fix
    # must not divert runs that do have a SmashRun activity behind them.
    with pytest.raises(AssertionError, match="must not be called"):
        _track(monkeypatch, polyline=encode_polyline(POINTS), source_type="smashrun")
