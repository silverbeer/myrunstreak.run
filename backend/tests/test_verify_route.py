"""SB-477: /verify — reconcile stored runs against SmashRun.

The diff itself is unit-tested in tests/test_verify.py; this covers the route's
own responsibilities — the window defaults, the guards that keep it inside the
ingress timeout, and normalising SmashRun activities for comparison.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException


def _activity(activity_id: str, day: str, km: float, seconds: float = 1800.0) -> SimpleNamespace:
    return SimpleNamespace(
        activity_id=activity_id,
        start_date_time_local=SimpleNamespace(date=lambda d=day: date.fromisoformat(d)),
        distance=km,
        duration=seconds,
    )


def _api_with(activities: list[SimpleNamespace]) -> MagicMock:
    api = MagicMock()
    api.__enter__ = MagicMock(return_value=api)
    api.__exit__ = MagicMock(return_value=False)
    api.get_all_activities_since.return_value = [{"raw": a.activity_id} for a in activities]
    api.parse_activity.side_effect = lambda raw: next(
        a for a in activities if a.activity_id == raw["raw"]
    )
    return api


def _run_verify(activities: list[SimpleNamespace], stored: list[dict], **kwargs: object) -> dict:
    repo = MagicMock()
    repo.get_runs_for_verify.return_value = stored
    with (
        patch("backend.routes.sync.get_supabase_client"),
        patch("backend.routes.sync.RunsRepository", return_value=repo),
        patch("backend.routes.sync.TokenRepository"),
        patch("backend.routes.sync._resolve_access_token", return_value="tok"),
        patch("backend.routes.sync.SmashRunAPIClient", return_value=_api_with(activities)),
    ):
        import asyncio

        from backend.routes.sync import verify_runs

        return asyncio.run(verify_runs(user_id=uuid4(), **kwargs))  # type: ignore[arg-type]


def _stored(activity_id: str, day: str, km: float, seconds: float = 1800.0) -> dict:
    return {
        "id": f"run-{activity_id}",
        "source_activity_id": activity_id,
        "start_date": day,
        "distance_km": km,
        "duration_seconds": seconds,
    }


def test_matching_range_is_clean() -> None:
    report = _run_verify(
        [_activity("1", "2024-12-01", 5.55113)],
        [_stored("1", "2024-12-01", 5.55113)],
        since="2024-12-01",
        until="2024-12-31",
    )

    assert report["clean"]
    assert report["matched"] == 1
    assert report["range"] == {"since": "2024-12-01", "until": "2024-12-31"}


def test_activities_outside_the_window_are_excluded() -> None:
    """get_all_activities_since walks forward to today, so everything after
    `until` comes back and must be dropped — otherwise a narrow window reports
    every later run as missing locally."""
    report = _run_verify(
        [
            _activity("1", "2024-12-15", 5.0),
            _activity("2", "2025-06-01", 6.0),  # after `until`
            _activity("3", "2024-11-30", 4.0),  # before `since`
        ],
        [_stored("1", "2024-12-15", 5.0)],
        since="2024-12-01",
        until="2024-12-31",
    )

    assert report["clean"]
    assert report["source_count"] == 1


def test_unparseable_activity_is_skipped_not_fatal() -> None:
    repo = MagicMock()
    repo.get_runs_for_verify.return_value = []
    api = MagicMock()
    api.__enter__ = MagicMock(return_value=api)
    api.__exit__ = MagicMock(return_value=False)
    api.get_all_activities_since.return_value = [{"raw": "bad"}]
    api.parse_activity.side_effect = ValueError("malformed")

    with (
        patch("backend.routes.sync.get_supabase_client"),
        patch("backend.routes.sync.RunsRepository", return_value=repo),
        patch("backend.routes.sync.TokenRepository"),
        patch("backend.routes.sync._resolve_access_token", return_value="tok"),
        patch("backend.routes.sync.SmashRunAPIClient", return_value=api),
    ):
        import asyncio

        from backend.routes.sync import verify_runs

        report = asyncio.run(verify_runs(user_id=uuid4(), since="2026-07-01"))  # type: ignore[arg-type]

    assert report["source_count"] == 0


def test_defaults_to_the_last_30_days() -> None:
    report = _run_verify([], [])
    today = date.today()
    assert report["range"]["until"] == today.isoformat()
    assert report["range"]["since"] == (today - timedelta(days=30)).isoformat()


def test_reversed_range_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        _run_verify([], [], since="2026-07-31", until="2026-07-01")
    assert exc.value.status_code == 422
    assert "on or before" in str(exc.value.detail)


def test_lookback_beyond_the_cap_is_rejected() -> None:
    """Cost scales with distance back from today, not window width: SmashRun
    pages newest-first, so a month in 2014 walks the whole history and would
    502 on the ingress timeout (SB-292)."""
    from backend.routes.sync import VERIFY_MAX_LOOKBACK_DAYS

    too_old = (date.today() - timedelta(days=VERIFY_MAX_LOOKBACK_DAYS + 1)).isoformat()

    with pytest.raises(HTTPException) as exc:
        _run_verify([], [], since=too_old)

    assert exc.value.status_code == 422
    assert "SB-292" in str(exc.value.detail)


def test_drift_is_reported_through_the_route() -> None:
    report = _run_verify(
        [_activity("1", "2024-12-01", 5.55113)],
        [_stored("1", "2024-12-01", 5.551)],
        since="2024-12-01",
        until="2024-12-31",
    )

    assert not report["clean"]
    assert report["distance_mismatches"][0]["source_km"] == 5.55113
