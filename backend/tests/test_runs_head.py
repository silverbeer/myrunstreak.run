"""Tests for GET /runs/head — the cheap version token for client cache gating."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from backend.routes import runs as runs_module

USER = uuid4()


class _Repo:
    """Stand-in for RunsRepository that records the head call."""

    def __init__(self, head: dict[str, Any]) -> None:
        self._head = head
        self.calls: list[Any] = []

    def __call__(self, _supabase: Any) -> _Repo:
        return self

    def get_runs_head(self, user_id: Any) -> dict[str, Any]:
        self.calls.append(user_id)
        return self._head


def test_runs_head_returns_count_and_latest(monkeypatch: Any) -> None:
    repo = _Repo({"count": 842, "latest_run_date": "2026-07-16T06:45:00"})
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", repo)

    out = asyncio.run(runs_module.runs_head(user_id=USER))

    assert out == {"count": 842, "latest_run_date": "2026-07-16T06:45:00"}
    assert repo.calls == [USER]  # scoped to the authenticated user


def test_runs_head_empty_history(monkeypatch: Any) -> None:
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", _Repo({"count": 0, "latest_run_date": None}))

    out = asyncio.run(runs_module.runs_head(user_id=USER))

    assert out == {"count": 0, "latest_run_date": None}
