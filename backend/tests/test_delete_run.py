"""SB-621: DELETE /runs/{activity_id} — remove an imported run."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from backend.routes import runs as runs_module
from fastapi import HTTPException

USER = uuid4()
RUN_ID = uuid4()
SOURCE_ID = uuid4()

_RUN = {
    "id": str(RUN_ID),
    "source_id": str(SOURCE_ID),
    "source_activity_id": "gpx-abc123",
    "timezone": "America/Denver",
    "start_date_time_local": "2026-08-08T10:50:35-04:00",
}


class _Repo:
    def __init__(self, run: dict[str, Any] | None, deleted: bool = True) -> None:
        self._run = run
        self._deleted = deleted
        self.delete_calls: list[tuple[Any, Any]] = []
        self.stats_calls: list[str] = []

    def __call__(self, _sb: Any) -> _Repo:
        return self

    def get_run_by_activity_id(self, _uid: Any, _aid: str) -> dict[str, Any] | None:
        return self._run

    def delete_run(self, user_id: Any, run_id: Any) -> bool:
        self.delete_calls.append((user_id, run_id))
        return self._deleted

    def recalculate_user_stats(self, _uid: Any, timezone: str = "UTC") -> None:
        self.stats_calls.append(timezone)


class _Users:
    def __init__(self, source_type: str) -> None:
        self._source_type = source_type

    def __call__(self, _sb: Any) -> _Users:
        return self

    def get_source_by_id(self, _sid: Any) -> dict[str, Any]:
        return {"source_type": self._source_type}


def _delete(
    monkeypatch: Any,
    *,
    run: dict[str, Any] | None = None,
    missing: bool = False,
    source_type: str = "import",
    deleted: bool = True,
) -> _Repo:
    repo = _Repo(None if missing else (run or _RUN), deleted=deleted)
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", repo)
    monkeypatch.setattr(runs_module, "UsersRepository", _Users(source_type))

    async def _no_cache(_uid: Any) -> int:
        return 0

    monkeypatch.setattr(runs_module, "invalidate_user", _no_cache)
    asyncio.run(runs_module.delete_run("gpx-abc123", user_id=USER))
    return repo


def test_deletes_an_imported_run(monkeypatch: Any) -> None:
    repo = _delete(monkeypatch)
    assert repo.delete_calls == [(USER, RUN_ID)]


def test_delete_is_scoped_to_the_caller(monkeypatch: Any) -> None:
    # The owner is passed down to the repository rather than being checked only
    # here — the backend holds the service-role key, so an unscoped delete by
    # id would reach any user's run.
    repo = _delete(monkeypatch)
    user_arg, _ = repo.delete_calls[0]
    assert user_arg == USER


def test_stats_are_recalculated_in_the_runs_own_timezone(monkeypatch: Any) -> None:
    repo = _delete(monkeypatch)
    assert repo.stats_calls == ["America/Denver"]


def test_stats_fall_back_when_the_run_has_no_timezone(monkeypatch: Any) -> None:
    repo = _delete(monkeypatch, run={**_RUN, "timezone": None})
    assert repo.stats_calls == [runs_module.DEFAULT_TIMEZONE]


def test_someone_elses_run_is_404_not_403(monkeypatch: Any) -> None:
    # get_run_by_activity_id is owner-scoped, so another user's id looks
    # identical to one that doesn't exist. A 403 would confirm it exists.
    with pytest.raises(HTTPException) as err:
        _delete(monkeypatch, missing=True)
    assert err.value.status_code == 404


def test_synced_run_is_refused_with_a_reason(monkeypatch: Any) -> None:
    with pytest.raises(HTTPException) as err:
        _delete(monkeypatch, source_type="smashrun")
    assert err.value.status_code == 409
    assert "comes back on the next sync" in err.value.detail


def test_synced_run_is_not_deleted(monkeypatch: Any) -> None:
    repo = _Repo(_RUN)
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", repo)
    monkeypatch.setattr(runs_module, "UsersRepository", _Users("smashrun"))

    with pytest.raises(HTTPException):
        asyncio.run(runs_module.delete_run("gpx-abc123", user_id=USER))

    assert repo.delete_calls == []
    assert repo.stats_calls == []


def test_losing_a_delete_race_is_404(monkeypatch: Any) -> None:
    # Two deletes of the same run: the second finds nothing to remove. The end
    # state is what was asked for, but the response should still be honest.
    with pytest.raises(HTTPException) as err:
        _delete(monkeypatch, deleted=False)
    assert err.value.status_code == 404


def test_stats_failure_does_not_resurrect_the_run(monkeypatch: Any) -> None:
    repo = _Repo(_RUN)
    monkeypatch.setattr(runs_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(runs_module, "RunsRepository", repo)
    monkeypatch.setattr(runs_module, "UsersRepository", _Users("import"))

    def _boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("rpc down")

    monkeypatch.setattr(repo, "recalculate_user_stats", _boom)

    async def _no_cache(_uid: Any) -> int:
        return 0

    monkeypatch.setattr(runs_module, "invalidate_user", _no_cache)

    # The run is already gone; a stats refresh failure must not surface as an
    # error that suggests otherwise.
    asyncio.run(runs_module.delete_run("gpx-abc123", user_id=USER))
    assert repo.delete_calls == [(USER, RUN_ID)]
