"""SB-293: GET /runs/{activity_id}/track — GPS track for the route-card map."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from backend.routes import runs as runs_module
from fastapi import HTTPException

USER = uuid4()

_RUN = {
    "id": str(uuid4()),
    "start_date_time_local": "2026-07-21T08:32:00",
    "distance_km": "6.88",
    "duration_seconds": "2498",
    "average_pace_min_per_km": "6.05",
    "weather_type": "cloudy",
    "temperature_celsius": "20.6",
}


class _Repo:
    def __init__(self, run: dict[str, Any] | None) -> None:
        self._run = run

    def __call__(self, _sb: Any) -> _Repo:
        return self

    def get_run_by_activity_id(self, _uid: Any, _aid: str) -> dict[str, Any] | None:
        return self._run


class _FakeApi:
    def __init__(self, detail: dict[str, Any]) -> None:
        self._detail = detail

    def __call__(self, *, access_token: str) -> _FakeApi:
        return self

    def __enter__(self) -> _FakeApi:
        return self

    def __exit__(self, *_a: Any) -> bool:
        return False

    def get_activity_by_id(self, _aid: str) -> dict[str, Any]:
        return self._detail


def _track(run: dict[str, Any] | None, detail: dict[str, Any], monkeypatch: Any) -> Any:
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", _Repo(run))
    monkeypatch.setattr(runs_module, "TokenRepository", lambda _sb: object())
    monkeypatch.setattr(runs_module, "_resolve_access_token", lambda _uid, _repo: "tok")
    monkeypatch.setattr(runs_module, "SmashRunAPIClient", _FakeApi(detail))
    return asyncio.run(runs_module.get_run_track("act-1", user_id=USER))


def test_track_returns_lat_lon_place_and_series(monkeypatch: Any) -> None:
    detail = {
        "recordingKeys": ["distance", "latitude", "longitude", "elevation", "heartRate", "clock"],
        "recordingValues": [
            [0.0, 0.1, 0.2],  # cumulative km
            [42.24, 42.25, 42.26],
            [-71.65, -71.66, -71.67],
            [10, 12, 11],  # elevation m
            [140, 150, 155],  # heart rate
            [0, 36, 74],  # clock seconds
        ],
        "city": "Worcester County",
        "state": "Massachusetts",
    }
    out = _track(_RUN, detail, monkeypatch)
    assert out["has_track"] is True
    assert out["lat"] == [42.24, 42.25, 42.26]
    assert out["lon"] == [-71.65, -71.66, -71.67]
    assert out["elevation_m"] == [10, 12, 11]
    assert out["heart_rate"] == [140, 150, 155]
    assert out["dist_km"] == [0.0, 0.1, 0.2]
    # Pace derived from distance+clock: last window 74s / 0.2km = 6.17 min/km.
    assert len(out["pace_min_per_km"]) == 3
    assert out["pace_min_per_km"][-1] == pytest.approx(74 / 60 / 0.2, abs=0.01)
    assert out["city"] == "Worcester County"
    # Stats come from our DB row (canonical), coerced to float.
    assert out["distance_km"] == 6.88
    assert out["avg_pace_min_per_km"] == 6.05


def test_track_empty_when_no_gps(monkeypatch: Any) -> None:
    detail = {"recordingKeys": ["distance", "clock"], "recordingValues": [[0, 1], [0, 5]]}
    out = _track(_RUN, detail, monkeypatch)
    assert out["has_track"] is False
    assert out["lat"] == []
    assert out["lon"] == []


def test_track_404_when_not_owned(monkeypatch: Any) -> None:
    with pytest.raises(HTTPException) as err:
        _track(None, {}, monkeypatch)
    assert err.value.status_code == 404
