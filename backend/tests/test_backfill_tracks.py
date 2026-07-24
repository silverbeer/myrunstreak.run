"""SB-310: track backfill is batched, rate-limited, resumable."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.routes import sync as sync_mod

USER = uuid4()


class _Repo:
    def __init__(self, pending: list[dict[str, Any]], remaining_after: int) -> None:
        self._pending = pending
        self._remaining_after = remaining_after
        self.stored: list[tuple[Any, str, int]] = []

    def __call__(self, _sb: Any) -> _Repo:
        return self

    def get_runs_missing_tracks(self, _uid: Any, limit: int = 100) -> list[dict[str, Any]]:
        return self._pending[:limit]

    def count_runs_missing_tracks(self, _uid: Any) -> int:
        return self._remaining_after

    def upsert_track(
        self, run_id: Any, polyline: str, point_count: int, precision: int = 5
    ) -> None:
        self.stored.append((run_id, polyline, point_count))


class _Api:
    def __init__(self, detail: dict[str, Any]) -> None:
        self._detail = detail

    def __call__(self, *, access_token: str) -> _Api:
        return self

    def __enter__(self) -> _Api:
        return self

    def __exit__(self, *_a: Any) -> bool:
        return False

    def get_activity_by_id(self, _aid: str) -> dict[str, Any]:
        return self._detail


def _wire(monkeypatch: Any, repo: _Repo, detail: dict[str, Any]) -> list[float]:
    slept: list[float] = []
    monkeypatch.setattr(sync_mod, "get_supabase_client", lambda: object())
    monkeypatch.setattr(sync_mod, "RunsRepository", repo)
    monkeypatch.setattr(sync_mod, "TokenRepository", lambda _sb: object())
    monkeypatch.setattr(sync_mod, "_resolve_access_token", lambda _uid, _repo: "tok")
    monkeypatch.setattr(sync_mod, "SmashRunAPIClient", _Api(detail))
    monkeypatch.setattr(sync_mod.time, "sleep", lambda s: slept.append(s))
    return slept


_TRACK_DETAIL = {
    "recordingKeys": ["latitude", "longitude"],
    "recordingValues": [[42.0, 42.1, 42.2], [-71.0, -71.0, -71.0]],
}


def test_backfill_stores_polylines_and_sleeps_between(monkeypatch: Any) -> None:
    pending = [
        {"id": str(uuid4()), "source_activity_id": "a1"},
        {"id": str(uuid4()), "source_activity_id": "a2"},
    ]
    repo = _Repo(pending, remaining_after=3)
    slept = _wire(monkeypatch, repo, _TRACK_DETAIL)

    out = sync_mod.backfill_user_tracks(USER, limit=100, sleep_seconds=0.4)

    assert out["runs_processed"] == 2
    assert out["tracks_stored"] == 2
    assert out["remaining"] == 3  # >0 -> call again
    assert len(repo.stored) == 2
    assert slept == [0.4, 0.4]  # rate-limited per run


def test_backfill_noop_when_nothing_pending(monkeypatch: Any) -> None:
    repo = _Repo([], remaining_after=0)
    _wire(monkeypatch, repo, _TRACK_DETAIL)
    out = sync_mod.backfill_user_tracks(USER)
    assert out == {"runs_processed": 0, "tracks_stored": 0, "remaining": 0}


def test_backfill_skips_run_without_gps_but_still_counts_processed(monkeypatch: Any) -> None:
    pending = [{"id": str(uuid4()), "source_activity_id": "a1"}]
    repo = _Repo(pending, remaining_after=0)
    _wire(monkeypatch, repo, {"recordingKeys": ["distance"], "recordingValues": [[0, 1]]})

    out = sync_mod.backfill_user_tracks(USER)
    # No lat/lon -> nothing stored, but the run was processed (won't be retried).
    assert out["runs_processed"] == 1
    assert out["tracks_stored"] == 0
    assert repo.stored == []


def test_backfill_survives_a_bad_activity(monkeypatch: Any) -> None:
    pending = [
        {"id": str(uuid4()), "source_activity_id": "bad"},
        {"id": str(uuid4()), "source_activity_id": "good"},
    ]
    repo = _Repo(pending, remaining_after=1)

    class _FlakyApi(_Api):
        def get_activity_by_id(self, aid: str) -> dict[str, Any]:
            if aid == "bad":
                raise RuntimeError("smashrun 500")
            return _TRACK_DETAIL

    monkeypatch.setattr(sync_mod, "get_supabase_client", lambda: object())
    monkeypatch.setattr(sync_mod, "RunsRepository", repo)
    monkeypatch.setattr(sync_mod, "TokenRepository", lambda _sb: object())
    monkeypatch.setattr(sync_mod, "_resolve_access_token", lambda _uid, _repo: "tok")
    monkeypatch.setattr(sync_mod, "SmashRunAPIClient", _FlakyApi(_TRACK_DETAIL))
    monkeypatch.setattr(sync_mod.time, "sleep", lambda _s: None)

    out = sync_mod.backfill_user_tracks(USER)
    # Bad one logged + skipped; good one stored.
    assert out["tracks_stored"] == 1
