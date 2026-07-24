"""SB-309: /track stores the simplified polyline; /tracks serves them."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from backend.routes import runs as runs_module

USER = uuid4()

_RUN = {
    "id": str(uuid4()),
    "start_date_time_local": "2026-07-21T08:32:00",
    "distance_km": "6.88",
    "duration_seconds": "2498",
    "average_pace_min_per_km": "6.05",
    "weather_type": "cloudy",
    "temperature_celsius": "20.6",
    "start_latitude": None,
    "start_longitude": None,
}


class _Repo:
    def __init__(self, run: dict[str, Any] | None) -> None:
        self._run = run
        self.stored: list[tuple[Any, str, int]] = []

    def __call__(self, _sb: Any) -> _Repo:
        return self

    def get_run_by_activity_id(self, _uid: Any, _aid: str) -> dict[str, Any] | None:
        return self._run

    def get_route_for_run(self, *_a: Any, **_k: Any) -> None:
        return None

    def upsert_track(
        self, run_id: Any, polyline: str, point_count: int, precision: int = 5
    ) -> None:
        self.stored.append((run_id, polyline, point_count))


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


def test_track_stores_simplified_polyline(monkeypatch: Any) -> None:
    # A track with a redundant collinear middle point -> stored, simplified.
    detail = {
        "recordingKeys": ["latitude", "longitude"],
        "recordingValues": [[42.0, 42.1, 42.2], [-71.0, -71.0, -71.0]],
    }
    repo = _Repo(_RUN)
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", repo)
    monkeypatch.setattr(runs_module, "TokenRepository", lambda _sb: object())
    monkeypatch.setattr(runs_module, "_resolve_access_token", lambda _uid, _repo: "tok")
    monkeypatch.setattr(runs_module, "SmashRunAPIClient", _FakeApi(detail))

    out = asyncio.run(runs_module.get_run_track("act-1", user_id=USER))

    assert out["has_track"] is True
    assert len(repo.stored) == 1
    run_id, polyline, n_pts = repo.stored[0]
    assert polyline  # non-empty encoded string
    assert n_pts == 2  # collinear middle point dropped


def test_track_store_failure_never_breaks_response(monkeypatch: Any) -> None:
    detail = {
        "recordingKeys": ["latitude", "longitude"],
        "recordingValues": [[42.0, 42.1], [-71.0, -71.1]],
    }

    class _BoomRepo(_Repo):
        def upsert_track(self, *_a: Any, **_k: Any) -> None:
            raise RuntimeError("db down")

    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", _BoomRepo(_RUN))
    monkeypatch.setattr(runs_module, "TokenRepository", lambda _sb: object())
    monkeypatch.setattr(runs_module, "_resolve_access_token", lambda _uid, _repo: "tok")
    monkeypatch.setattr(runs_module, "SmashRunAPIClient", _FakeApi(detail))

    # Storage blew up, but the track response still comes back.
    out = asyncio.run(runs_module.get_run_track("act-1", user_id=USER))
    assert out["has_track"] is True
    assert out["lat"] == [42.0, 42.1]


class _TracksRepo:
    def __init__(self, tracks: list[dict[str, Any]]) -> None:
        self._tracks = tracks

    def __call__(self, _sb: Any) -> _TracksRepo:
        return self

    def get_all_track_polylines(self, user_id: Any) -> list[dict[str, Any]]:
        assert user_id == USER
        return self._tracks


def test_tracks_endpoint_shape(monkeypatch: Any) -> None:
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(
        runs_module,
        "RunsRepository",
        _TracksRepo([{"polyline": "abc", "encoded_precision": 5}]),
    )
    out = asyncio.run(runs_module.all_tracks(user_id=USER))
    assert out == {"count": 1, "tracks": [{"polyline": "abc", "encoded_precision": 5}]}
