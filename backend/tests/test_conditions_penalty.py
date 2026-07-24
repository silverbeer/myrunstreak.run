"""SB-304: hot+humid pace penalty from history — repo + endpoint."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from backend.routes import runs as runs_module
from src.shared.supabase_ops.runs_repository import RunsRepository

USER = uuid4()


class _FakeQuery:
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


def _run(pace: float, temp: float | None, humidity: float | None) -> dict[str, Any]:
    return {
        "average_pace_min_per_km": pace,
        "temperature_celsius": temp,
        "humidity_percent": humidity,
    }


def test_penalty_is_steamy_minus_baseline_median() -> None:
    rows = (
        # steamy (>=24C & >=70%): median pace 6.5 min/km
        [_run(6.4, 26, 80), _run(6.5, 27, 85), _run(6.6, 25, 72)]
        # baseline: median pace 6.0
        + [_run(5.9, 15, 50), _run(6.0, 18, 60), _run(6.1, 20, 65)]
    )
    out = _repo(rows).get_conditions_penalty(USER, min_steamy=3)
    assert out is not None
    assert out["steamy_run_count"] == 3
    assert out["baseline_run_count"] == 3
    # (6.5 - 6.0) min/km -> sec/mi
    assert out["penalty_sec_per_mi"] == round(0.5 * 1.609344 * 60)


def test_none_when_too_few_steamy_runs() -> None:
    rows = [_run(6.4, 26, 80)] + [_run(6.0, 15, 50) for _ in range(10)]
    assert _repo(rows).get_conditions_penalty(USER, min_steamy=5) is None


def test_runs_missing_weather_count_as_baseline() -> None:
    # A run with null temp/humidity can't be steamy -> baseline side.
    rows = [
        _run(6.5, 26, 80),
        _run(6.5, 26, 80),
        _run(6.5, 26, 80),
        _run(6.5, 26, 80),
        _run(6.5, 26, 80),
        _run(6.0, None, None),
    ]
    out = _repo(rows).get_conditions_penalty(USER, min_steamy=5)
    assert out is not None
    assert out["steamy_run_count"] == 5
    assert out["baseline_run_count"] == 1


class _EndpointRepo:
    def __init__(self, penalty: dict[str, Any] | None) -> None:
        self._penalty = penalty

    def __call__(self, _sb: Any) -> _EndpointRepo:
        return self

    def get_conditions_penalty(self, _uid: Any) -> dict[str, Any] | None:
        return self._penalty


def test_endpoint_available_true_when_penalty(monkeypatch: Any) -> None:
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", _EndpointRepo({"penalty_sec_per_mi": 25}))
    out = asyncio.run(runs_module.conditions_penalty(user_id=USER))
    assert out == {"available": True, "penalty_sec_per_mi": 25}


def test_endpoint_available_false_when_none(monkeypatch: Any) -> None:
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", _EndpointRepo(None))
    out = asyncio.run(runs_module.conditions_penalty(user_id=USER))
    assert out == {"available": False}
