"""Tests for GET /runs/{activity_id} (SB-263 run detail)."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from backend.routes import runs as runs_module
from fastapi import HTTPException

USER = uuid4()
RUN_ID = str(uuid4())

_RUN = {
    "id": RUN_ID,
    "source_activity_id": "act-123",
    "start_date_time_local": "2026-07-10T06:45:00",
    "distance_km": "5.31",
    "duration_seconds": "3141",
    "average_pace_min_per_km": "9.86",
    "temperature_celsius": "27.8",
    "weather_type": "hot",
    "humidity_percent": 82,
    "wind_speed_kph": 9,
    "heart_rate_average": "151",
    "heart_rate_min": "128",
    "heart_rate_max": "167",
    "cadence_average": "169",
    "how_felt": None,
    "notes": None,
}

_SPLITS = [
    {
        "split_number": 2,
        "split_unit": "mi",
        "cumulative_distance_km": "3.219",
        "cumulative_seconds": "1254",
        "pace_min_per_km": "9.98",
        "heart_rate": 150,
        "cumulative_elevation_gain_meters": "29",
        "cumulative_elevation_loss_meters": "15",
    },
    {
        "split_number": 1,
        "split_unit": "mi",
        "cumulative_distance_km": "1.609",
        "cumulative_seconds": "612",
        "pace_min_per_km": "9.51",
        "heart_rate": 142,
        "cumulative_elevation_gain_meters": "12",
        "cumulative_elevation_loss_meters": "4",
    },
]


class _Repo:
    def __init__(self, run: dict[str, Any] | None, splits: list[dict[str, Any]]):
        self._run, self._splits = run, splits

    def __call__(self, _supabase: Any) -> _Repo:
        return self

    def get_run_by_activity_id(self, user_id: Any, activity_id: str) -> dict[str, Any] | None:
        return self._run

    def get_splits_for_run(self, run_id: Any) -> list[dict[str, Any]]:
        return self._splits


def _detail(run: dict[str, Any] | None, splits: list[dict[str, Any]], monkeypatch: Any) -> Any:
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", _Repo(run, splits))
    return asyncio.run(runs_module.get_run_detail("act-123", user_id=USER))


def test_detail_shapes_weather_vitals_and_sorted_splits(monkeypatch: Any) -> None:
    out = _detail(_RUN, _SPLITS, monkeypatch)
    assert out["weather"] == {
        "temperature_celsius": 27.8,
        "weather_type": "hot",
        "humidity_percent": 82,
        "wind_speed_kph": 9,
    }
    assert out["vitals"]["heart_rate_max"] == 167.0
    # Splits sorted by split_number, numerics coerced to float.
    assert [s["split_number"] for s in out["splits"]] == [1, 2]
    assert out["splits"][0]["pace_min_per_km"] == 9.51
    assert out["splits"][1]["elevation_gain_m"] == 29.0


def test_detail_404_when_not_owned(monkeypatch: Any) -> None:
    with pytest.raises(HTTPException) as err:
        _detail(None, [], monkeypatch)
    assert err.value.status_code == 404
