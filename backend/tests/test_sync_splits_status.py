"""SB-184: read-only splits-backfill status endpoint + the count it uses."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.shared.supabase_ops.runs_repository import RunsRepository


class _CountQuery:
    def __init__(self, count: int | None) -> None:
        self._count = count

    def select(self, *a: Any, **k: Any) -> _CountQuery:
        return self

    def eq(self, *a: Any, **k: Any) -> _CountQuery:
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=[], count=self._count)


class _Client:
    def __init__(self, count: int | None) -> None:
        self._count = count

    def table(self, _name: str) -> _CountQuery:
        return _CountQuery(self._count)


def test_count_runs_missing_splits() -> None:
    repo = RunsRepository(_Client(2860))  # type: ignore[arg-type]
    assert repo.count_runs_missing_splits(uuid4()) == 2860


def test_count_runs_missing_splits_none_is_zero() -> None:
    repo = RunsRepository(_Client(None))  # type: ignore[arg-type]
    assert repo.count_runs_missing_splits(uuid4()) == 0


async def test_status_endpoint_reports_progress() -> None:
    from backend.routes.sync import sync_splits_status

    repo = MagicMock()
    repo.count_runs_by_user.return_value = 4700
    repo.count_runs_missing_splits.return_value = 2860

    with (
        patch("backend.routes.sync.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.sync.RunsRepository", return_value=repo),
    ):
        out = await sync_splits_status(user_id=uuid4())

    assert out["runs_total"] == 4700
    assert out["runs_with_splits"] == 1840
    assert out["runs_missing_splits"] == 2860
    assert out["pct_complete"] == 39.1
    assert out["done"] is False


async def test_status_endpoint_done_when_none_missing() -> None:
    from backend.routes.sync import sync_splits_status

    repo = MagicMock()
    repo.count_runs_by_user.return_value = 4700
    repo.count_runs_missing_splits.return_value = 0

    with (
        patch("backend.routes.sync.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.sync.RunsRepository", return_value=repo),
    ):
        out = await sync_splits_status(user_id=uuid4())

    assert out["done"] is True
    assert out["pct_complete"] == 100.0
