"""Route-handler tests for /plan/* via FastAPI TestClient.

Auth is bypassed with ``app.dependency_overrides[authenticate_request]`` (a
fixed user_id) and every repository / planner call in ``backend.routes.plan``
is patched, so nothing touches Supabase. CACHE_ENABLED=false (conftest) makes
``invalidate_user`` a no-op.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

USER_ID = UUID("00000000-0000-0000-0000-0000000000aa")

_METRIC_TYPE = {
    "key": "distance_km",
    "display_name": "Distance",
    "unit": "km",
    "aggregation": "sum",
}


@pytest.fixture
def client() -> Iterator[TestClient]:
    from backend.app import create_app
    from backend.auth import authenticate_request

    app = create_app()
    app.dependency_overrides[authenticate_request] = lambda: USER_ID
    yield TestClient(app)
    app.dependency_overrides.clear()


def _plan_result(period_start: date, period_end: date) -> dict[str, object]:
    """A minimal PlanResult-shaped dict the response_model accepts."""
    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "generated_for": period_start.isoformat(),
        "days": [
            {
                "metric_key": "distance_km",
                "plan_on": period_start.isoformat(),
                "prescribed_value": 5.0,
                "kind": "easy",
            }
        ],
        "goals": [
            {
                "metric_key": "distance_km",
                "kind": "volume",
                "target": 100.0,
                "done": 20.0,
                "remaining": 80.0,
                "projected": 105.0,
                "status": "on_track",
                "detail": None,
            }
        ],
        "status": "on_track",
        "at_risk_reasons": [],
    }


# ---------------------------------------------------------------- constraints


def test_create_constraint_rejects_unknown_metric(client: TestClient) -> None:
    types = MagicMock()
    types.get.return_value = None
    constraints = MagicMock()

    with (
        patch("backend.routes.plan.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.plan.MetricTypesRepository", return_value=types),
        patch("backend.routes.plan.PlanConstraintsRepository", return_value=constraints),
    ):
        r = client.post(
            "/plan/constraints",
            json={
                "metric_key": "nope",
                "start_on": "2026-07-01",
                "end_on": "2026-07-05",
                "cap": 1.6,
            },
        )

    assert r.status_code == 400
    assert "nope" in r.json()["detail"]
    constraints.create.assert_not_called()


def test_create_constraint_persists_and_returns_record(client: TestClient) -> None:
    types = MagicMock()
    types.get.return_value = _METRIC_TYPE
    row_id = uuid4()
    constraints = MagicMock()
    constraints.create.side_effect = lambda user_id, payload: {"id": str(row_id), **payload}

    with (
        patch("backend.routes.plan.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.plan.MetricTypesRepository", return_value=types),
        patch("backend.routes.plan.PlanConstraintsRepository", return_value=constraints),
    ):
        r = client.post(
            "/plan/constraints",
            json={
                "metric_key": "distance_km",
                "start_on": "2026-07-01",
                "end_on": "2026-07-05",
                "cap": 1.6,
                "floor": 1.6,
                "reason": "Chicago trip",
            },
        )

    assert r.status_code == 201
    body = r.json()
    assert body["id"] == str(row_id)
    assert body["metric_key"] == "distance_km"
    assert body["cap"] == 1.6

    # user_id from the auth dependency, payload without the None fields.
    assert constraints.create.call_args.args[0] == USER_ID
    payload = constraints.create.call_args.args[1]
    assert payload["start_on"] == "2026-07-01"
    assert payload["reason"] == "Chicago trip"


def test_create_constraint_422_when_end_before_start(client: TestClient) -> None:
    # Model validation rejects it before any repo is touched.
    with patch("backend.routes.plan.get_supabase_client", return_value=MagicMock()) as supa:
        r = client.post(
            "/plan/constraints",
            json={"metric_key": "distance_km", "start_on": "2026-07-05", "end_on": "2026-07-01"},
        )

    assert r.status_code == 422
    supa.assert_not_called()


def test_list_constraints_passes_date_filters(client: TestClient) -> None:
    row = {
        "id": str(uuid4()),
        "metric_key": "distance_km",
        "start_on": "2026-07-01",
        "end_on": "2026-07-05",
        "cap": 1.6,
        "floor": None,
        "reason": None,
    }
    constraints = MagicMock()
    constraints.list.return_value = [row]

    with (
        patch("backend.routes.plan.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.plan.PlanConstraintsRepository", return_value=constraints),
    ):
        r = client.get(
            "/plan/constraints", params={"date_from": "2026-07-01", "date_to": "2026-07-31"}
        )

    assert r.status_code == 200
    assert [c["id"] for c in r.json()] == [row["id"]]
    constraints.list.assert_called_once_with(
        USER_ID, date_from=date(2026, 7, 1), date_to=date(2026, 7, 31)
    )


def test_list_constraints_without_filters_passes_none(client: TestClient) -> None:
    constraints = MagicMock()
    constraints.list.return_value = []

    with (
        patch("backend.routes.plan.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.plan.PlanConstraintsRepository", return_value=constraints),
    ):
        r = client.get("/plan/constraints")

    assert r.status_code == 200
    assert r.json() == []
    constraints.list.assert_called_once_with(USER_ID, date_from=None, date_to=None)


def test_delete_constraint_204_when_deleted(client: TestClient) -> None:
    constraint_id = uuid4()
    constraints = MagicMock()
    constraints.delete.return_value = True

    with (
        patch("backend.routes.plan.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.plan.PlanConstraintsRepository", return_value=constraints),
    ):
        r = client.delete(f"/plan/constraints/{constraint_id}")

    assert r.status_code == 204
    constraints.delete.assert_called_once_with(USER_ID, constraint_id)


def test_delete_constraint_404_when_missing(client: TestClient) -> None:
    constraints = MagicMock()
    constraints.delete.return_value = False

    with (
        patch("backend.routes.plan.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.plan.PlanConstraintsRepository", return_value=constraints),
    ):
        r = client.delete(f"/plan/constraints/{uuid4()}")

    assert r.status_code == 404
    assert r.json()["detail"] == "Constraint not found"


# ---------------------------------------------------------------- readiness


def test_set_readiness_upserts_and_returns_recomputed_plan(client: TestClient) -> None:
    readiness = MagicMock()
    result = _plan_result(date(2026, 7, 1), date(2026, 7, 31))

    with (
        patch("backend.routes.plan.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.plan.ReadinessRepository", return_value=readiness),
        patch("backend.routes.plan.build_and_store_plan", return_value=result) as build,
    ):
        r = client.post(
            "/plan/readiness",
            json={"log_on": "2026-07-14", "status": "tired", "note": "long day"},
        )

    assert r.status_code == 200
    assert r.json()["status"] == "on_track"

    assert readiness.upsert.call_args.args[0] == USER_ID
    payload = readiness.upsert.call_args.args[1]
    assert payload == {"log_on": "2026-07-14", "status": "tired", "note": "long day"}

    # The plan is recomputed for the period the readiness day falls in.
    assert build.call_args.args[2] == "2026-07"


def test_set_readiness_defaults_status_to_good(client: TestClient) -> None:
    readiness = MagicMock()
    result = _plan_result(date(2026, 7, 1), date(2026, 7, 31))

    with (
        patch("backend.routes.plan.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.plan.ReadinessRepository", return_value=readiness),
        patch("backend.routes.plan.build_and_store_plan", return_value=result),
    ):
        r = client.post("/plan/readiness", json={"log_on": "2026-07-14"})

    assert r.status_code == 200
    assert readiness.upsert.call_args.args[1]["status"] == "good"


# ---------------------------------------------------------------- the plan


def test_get_plan_returns_recomputed_result(client: TestClient) -> None:
    result = _plan_result(date(2026, 7, 1), date(2026, 7, 31))

    with (
        patch("backend.routes.plan.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.plan.build_plan", return_value=result) as build,
    ):
        r = client.get("/plan/2026-07")

    assert r.status_code == 200
    body = r.json()
    assert body["period_start"] == "2026-07-01"
    assert body["days"][0]["metric_key"] == "distance_km"
    assert build.call_args.args[1] == USER_ID
    assert build.call_args.args[2] == "2026-07"


def test_get_plan_400_on_bad_period(client: TestClient) -> None:
    with (
        patch("backend.routes.plan.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.plan.build_plan", side_effect=ValueError("period must be 'YYYY-MM'")),
    ):
        r = client.get("/plan/not-a-period")

    assert r.status_code == 400
    assert "YYYY-MM" in r.json()["detail"]


def test_recompute_plan_persists_and_returns_result(client: TestClient) -> None:
    result = _plan_result(date(2026, 7, 1), date(2026, 7, 31))

    with (
        patch("backend.routes.plan.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.plan.build_and_store_plan", return_value=result) as build,
    ):
        r = client.post("/plan/2026-07/recompute")

    assert r.status_code == 200
    assert r.json()["status"] == "on_track"
    build.assert_called_once()
    assert build.call_args.args[1] == USER_ID
    assert build.call_args.args[2] == "2026-07"


def test_recompute_plan_400_on_bad_period(client: TestClient) -> None:
    with (
        patch("backend.routes.plan.get_supabase_client", return_value=MagicMock()),
        patch(
            "backend.routes.plan.build_and_store_plan",
            side_effect=ValueError("month out of range in period '2026-13'"),
        ),
    ):
        r = client.post("/plan/2026-13/recompute")

    assert r.status_code == 400
    assert "out of range" in r.json()["detail"]


def test_plan_routes_require_auth() -> None:
    """Without the dependency override the real JWT dependency rejects the call."""
    from backend.app import create_app

    with TestClient(create_app()) as unauthed:
        assert unauthed.get("/plan/2026-07").status_code == 401
        assert unauthed.get("/plan/constraints").status_code == 401
