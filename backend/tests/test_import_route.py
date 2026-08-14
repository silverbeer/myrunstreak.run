"""SB-99: POST /import/activity — single activity file import."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from backend.routes import imports as imports_module
from fastapi import HTTPException

USER = uuid4()
SOURCE_ID = uuid4()
RUN_ID = uuid4()

GPX = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Test" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Morning Run</name><trkseg>
    <trkpt lat="42.2400" lon="-71.6500"><time>2026-08-10T11:00:00Z</time></trkpt>
    <trkpt lat="42.2410" lon="-71.6500"><time>2026-08-10T11:01:00Z</time></trkpt>
    <trkpt lat="42.2420" lon="-71.6500"><time>2026-08-10T11:02:00Z</time></trkpt>
  </trkseg></trk>
</gpx>
"""

SMASHRUN = json.dumps(
    {
        "activityId": 4242,
        "startDateTimeLocal": "2026-08-10T07:15:00-04:00",
        "distance": 8.05,
        "duration": 2700.0,
    }
).encode()


class _Upload:
    """Enough of starlette's UploadFile for the route: a name and async read."""

    def __init__(self, filename: str | None, data: bytes) -> None:
        self.filename = filename
        self._data = data
        self._offset = 0

    async def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk, self._offset = self._data[self._offset :], len(self._data)
            return chunk
        chunk = self._data[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


class _RunsRepo:
    def __init__(self, existing: dict[str, Any] | None = None) -> None:
        self.existing = existing
        self.upserted: dict[str, Any] | None = None
        self.tracks: list[tuple[UUID, str, int]] = []
        self.stats_calls: list[str] = []

    def __call__(self, _sb: Any) -> _RunsRepo:
        return self

    def get_run_by_activity_id(self, _uid: UUID, _aid: str) -> dict[str, Any] | None:
        return self.existing

    def upsert_run(self, _uid: UUID, _sid: UUID, run_data: dict[str, Any]) -> dict[str, Any]:
        self.upserted = run_data
        return {"id": str(RUN_ID), **run_data}

    def upsert_track(self, run_id: UUID, polyline: str, point_count: int) -> None:
        self.tracks.append((run_id, polyline, point_count))

    def recalculate_user_stats(self, _uid: UUID, timezone: str = "UTC") -> None:
        self.stats_calls.append(timezone)


class _UsersRepo:
    def __init__(self) -> None:
        self.created: list[tuple[UUID, str, str | None]] = []

    def __call__(self, _sb: Any) -> _UsersRepo:
        return self

    def get_or_create_source(
        self, user_id: UUID, source_type: str, source_username: str | None = None
    ) -> UUID:
        self.created.append((user_id, source_type, source_username))
        return SOURCE_ID


@pytest.fixture
def repos(monkeypatch: Any) -> tuple[_RunsRepo, _UsersRepo]:
    runs_repo, users_repo = _RunsRepo(), _UsersRepo()
    monkeypatch.setattr(imports_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(imports_module, "RunsRepository", runs_repo)
    monkeypatch.setattr(imports_module, "UsersRepository", users_repo)

    async def _no_cache(_uid: UUID) -> int:
        return 0

    monkeypatch.setattr(imports_module, "invalidate_user", _no_cache)
    return runs_repo, users_repo


async def _import(
    filename: str | None,
    data: bytes,
    timezone: str = "America/New_York",
) -> dict[str, Any]:
    return await imports_module.import_activity(
        user_id=USER, file=_Upload(filename, data), timezone=timezone
    )


async def test_gpx_upload_creates_a_run_and_a_track(repos: tuple[_RunsRepo, _UsersRepo]) -> None:
    runs_repo, users_repo = repos
    out = await _import("run.gpx", GPX)

    assert out["status"] == "imported"
    assert out["run_id"] == str(RUN_ID)
    assert out["has_track"] is True
    assert users_repo.created == [(USER, "import", "file-import")]
    assert runs_repo.tracks and runs_repo.tracks[0][0] == RUN_ID


async def test_imported_run_is_scoped_to_the_caller(repos: tuple[_RunsRepo, _UsersRepo]) -> None:
    runs_repo, _ = repos
    await _import("run.gpx", GPX)
    assert runs_repo.upserted is not None
    assert runs_repo.upserted["user_id"] == str(USER)
    assert runs_repo.upserted["source_id"] == str(SOURCE_ID)


async def test_local_date_comes_from_the_requested_timezone(
    repos: tuple[_RunsRepo, _UsersRepo],
) -> None:
    runs_repo, _ = repos
    # 11:00 UTC is 04:00 in Los Angeles — still the 10th, but a different hour,
    # and the stored zone has to say which reading produced the date.
    await _import("run.gpx", GPX, timezone="America/Los_Angeles")
    assert runs_repo.upserted is not None
    assert runs_repo.upserted["start_date"] == "2026-08-10"
    assert runs_repo.upserted["start_hour"] == 4
    assert runs_repo.upserted["timezone"] == "America/Los_Angeles"
    assert runs_repo.stats_calls == ["America/Los_Angeles"]


async def test_reupload_is_reported_as_duplicate_not_an_error(monkeypatch: Any) -> None:
    existing = {
        "id": str(RUN_ID),
        "distance_km": "0.222",
        "duration_seconds": "120",
        "start_date_time_local": "2026-08-10T07:00:00-04:00",
        "has_gps_data": True,
    }
    runs_repo, users_repo = _RunsRepo(existing=existing), _UsersRepo()
    monkeypatch.setattr(imports_module, "get_supabase_client", lambda: object())
    monkeypatch.setattr(imports_module, "RunsRepository", runs_repo)
    monkeypatch.setattr(imports_module, "UsersRepository", users_repo)

    out = await _import("run.gpx", GPX)

    assert out["status"] == "duplicate"
    assert out["run_id"] == str(RUN_ID)
    # Nothing was written: no source created, no upsert, no track.
    assert users_repo.created == []
    assert runs_repo.upserted is None
    assert runs_repo.tracks == []


async def test_smashrun_json_upload_has_no_track(repos: tuple[_RunsRepo, _UsersRepo]) -> None:
    runs_repo, _ = repos
    out = await _import("export.json", SMASHRUN)
    assert out["status"] == "imported"
    assert out["has_track"] is False
    assert runs_repo.tracks == []


async def test_wrong_file_type_is_415(repos: tuple[_RunsRepo, _UsersRepo]) -> None:
    with pytest.raises(HTTPException) as err:
        await _import("photo.png", b"\x89PNG")
    assert err.value.status_code == 415
    assert "Supported formats" in err.value.detail


async def test_oversized_upload_is_413_and_stops_reading(
    repos: tuple[_RunsRepo, _UsersRepo],
) -> None:
    oversized = b"x" * (imports_module.MAX_UPLOAD_BYTES + 1024)
    with pytest.raises(HTTPException) as err:
        await _import("run.gpx", oversized)
    assert err.value.status_code == 413


async def test_unparseable_file_is_422_with_a_readable_reason(
    repos: tuple[_RunsRepo, _UsersRepo],
) -> None:
    with pytest.raises(HTTPException) as err:
        await _import("run.gpx", b"<gpx><trk>")
    assert err.value.status_code == 422
    assert "not valid XML" in err.value.detail


async def test_missing_filename_is_400(repos: tuple[_RunsRepo, _UsersRepo]) -> None:
    with pytest.raises(HTTPException) as err:
        await _import(None, GPX)
    assert err.value.status_code == 400


async def test_stats_failure_does_not_fail_the_import(
    repos: tuple[_RunsRepo, _UsersRepo], monkeypatch: Any
) -> None:
    runs_repo, _ = repos

    def _boom(_uid: UUID, timezone: str = "UTC") -> None:
        raise RuntimeError("rpc down")

    monkeypatch.setattr(runs_repo, "recalculate_user_stats", _boom)
    out = await _import("run.gpx", GPX)
    assert out["status"] == "imported"


async def test_formats_endpoint_states_the_limits() -> None:
    out = await imports_module.import_formats(_user_id=USER)
    assert out["extensions"] == [".gpx", ".json", ".tcx"]
    assert out["max_bytes"] == imports_module.MAX_UPLOAD_BYTES
