"""Route-handler tests for GET /stats/splits via FastAPI TestClient.

Auth is bypassed with ``app.dependency_overrides[authenticate_request]`` and
``RunsRepository`` is mocked, so the real split-analysis math runs over
fixture rows without touching Supabase.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

USER_ID = UUID("00000000-0000-0000-0000-0000000000bb")


@pytest.fixture
def client() -> Iterator[TestClient]:
    from backend.app import create_app
    from backend.auth import authenticate_request

    app = create_app()
    app.dependency_overrides[authenticate_request] = lambda: USER_ID
    yield TestClient(app)
    app.dependency_overrides.clear()


def _splits(*pieces: tuple[float, float]) -> list[dict[str, Any]]:
    """Build cumulative split rows from per-mile (distance_km, seconds) pieces."""
    rows: list[dict[str, Any]] = []
    cum_km = 0.0
    cum_s = 0.0
    for i, (km, secs) in enumerate(pieces, start=1):
        cum_km += km
        cum_s += secs
        rows.append(
            {
                "split_number": i,
                "cumulative_distance_km": cum_km,
                "cumulative_seconds": cum_s,
                "heart_rate": None,
            }
        )
    return rows


MILE_KM = 1.60934


def test_splits_empty_when_no_runs_have_splits(client: TestClient) -> None:
    repo = MagicMock()
    repo.get_runs_with_splits.return_value = []

    with (
        patch("backend.routes.stats.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.stats.RunsRepository", return_value=repo),
    ):
        r = client.get("/stats/splits")

    assert r.status_code == 200
    assert r.json() == {"summary": {"runs_analyzed": 0}, "runs": []}
    repo.get_splits_for_run.assert_not_called()


def test_splits_populated_summarizes_and_breaks_down_per_run(client: TestClient) -> None:
    neg_id, fade_id = str(uuid4()), str(uuid4())
    repo = MagicMock()
    repo.get_runs_with_splits.return_value = [
        {"id": neg_id, "start_date": "2026-07-10", "distance_km": 2 * MILE_KM},
        {"id": fade_id, "start_date": "2026-07-11", "distance_km": 2 * MILE_KM},
    ]
    by_run = {
        # 10:00 then 9:00 → negative split.
        UUID(neg_id): _splits((MILE_KM, 600.0), (MILE_KM, 540.0)),
        # 9:00 then 10:00 → fade.
        UUID(fade_id): _splits((MILE_KM, 540.0), (MILE_KM, 600.0)),
    }
    repo.get_splits_for_run.side_effect = lambda run_id: by_run[run_id]

    with (
        patch("backend.routes.stats.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.stats.RunsRepository", return_value=repo),
    ):
        r = client.get("/stats/splits")

    assert r.status_code == 200
    body = r.json()

    assert body["summary"]["runs_analyzed"] == 2
    assert body["summary"]["negative_split_rate_pct"] == 50.0

    assert [run["run_id"] for run in body["runs"]] == [neg_id, fade_id]
    negative, fading = body["runs"]
    assert negative["negative_split"] is True
    assert negative["fade_pct"] < 0
    assert negative["date"] == "2026-07-10"
    assert negative["distance_km"] == pytest.approx(2 * MILE_KM)
    assert fading["negative_split"] is False
    assert fading["fade_pct"] > 0

    # The per-run breakdown drops the raw split list (summary payload only).
    assert "splits" not in negative


def test_splits_skips_runs_with_fewer_than_two_usable_splits(client: TestClient) -> None:
    single_id, pair_id = str(uuid4()), str(uuid4())
    repo = MagicMock()
    repo.get_runs_with_splits.return_value = [
        {"id": single_id, "start_date": "2026-07-10", "distance_km": MILE_KM},
        {"id": pair_id, "start_date": "2026-07-11", "distance_km": 2 * MILE_KM},
    ]
    by_run = {
        UUID(single_id): _splits((MILE_KM, 600.0)),
        UUID(pair_id): _splits((MILE_KM, 600.0), (MILE_KM, 540.0)),
    }
    repo.get_splits_for_run.side_effect = lambda run_id: by_run[run_id]

    with (
        patch("backend.routes.stats.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.stats.RunsRepository", return_value=repo),
    ):
        r = client.get("/stats/splits")

    assert r.status_code == 200
    body = r.json()
    assert [run["run_id"] for run in body["runs"]] == [pair_id]
    assert body["summary"]["runs_analyzed"] == 1


def test_splits_passes_query_filters_through(client: TestClient) -> None:
    repo = MagicMock()
    repo.get_runs_with_splits.return_value = []

    with (
        patch("backend.routes.stats.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.stats.RunsRepository", return_value=repo),
    ):
        r = client.get(
            "/stats/splits",
            params={"since": "2026-06-01", "until": "2026-06-30", "limit": 5},
        )

    assert r.status_code == 200
    repo.get_runs_with_splits.assert_called_once_with(
        USER_ID, since=date(2026, 6, 1), until=date(2026, 6, 30), limit=5
    )


def test_splits_defaults_limit_to_30(client: TestClient) -> None:
    repo = MagicMock()
    repo.get_runs_with_splits.return_value = []

    with (
        patch("backend.routes.stats.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.stats.RunsRepository", return_value=repo),
    ):
        client.get("/stats/splits")

    assert repo.get_runs_with_splits.call_args.kwargs["limit"] == 30


@pytest.mark.parametrize("limit", [0, 201])
def test_splits_rejects_out_of_range_limit(client: TestClient, limit: int) -> None:
    with patch("backend.routes.stats.get_supabase_client", return_value=MagicMock()) as supa:
        r = client.get("/stats/splits", params={"limit": limit})

    assert r.status_code == 422
    supa.assert_not_called()


def test_splits_requires_auth() -> None:
    from backend.app import create_app

    with TestClient(create_app()) as unauthed:
        assert unauthed.get("/stats/splits").status_code == 401
