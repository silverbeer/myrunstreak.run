"""SB-275: an invalid weather_type must be rejected, not 500.

weather_type is a Postgres enum. An unknown value used to reach PostgREST,
fail the cast, and surface as an unhandled 500 — e.g. `stk summary --weather
rain` (the valid value is `rainy`).

The existing filter tests (test_run_filters.py) cover the repository layer with
valid input only, so nothing exercised the route with a bad value.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from src.shared.supabase_ops.mappers import WEATHER_TYPE_MAP, WEATHER_TYPES

USER_ID = UUID("00000000-0000-0000-0000-0000000000cc")


@pytest.fixture
def client() -> Iterator[TestClient]:
    from backend.app import create_app
    from backend.auth import authenticate_request

    app = create_app()
    app.dependency_overrides[authenticate_request] = lambda: USER_ID
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("endpoint", ["/runs", "/runs/summary"])
def test_invalid_weather_type_is_422_not_500(client: TestClient, endpoint: str) -> None:
    """The repro from the ticket: 'rain' is not the enum value 'rainy'."""
    r = client.get(endpoint, params={"weather_type": "rain"})

    assert r.status_code == 422, f"{endpoint} returned {r.status_code}"
    # The rejection has to name the allowed values, or the caller is guessing.
    assert "rainy" in r.text


@pytest.mark.parametrize("endpoint", ["/runs", "/runs/summary"])
def test_empty_string_is_rejected(client: TestClient, endpoint: str) -> None:
    """An empty filter is a caller bug, not 'no filter' — don't cast it."""
    assert client.get(endpoint, params={"weather_type": ""}).status_code == 422


@pytest.mark.parametrize("endpoint", ["/runs", "/runs/summary"])
def test_sql_injection_shaped_value_is_rejected(client: TestClient, endpoint: str) -> None:
    assert (
        client.get(endpoint, params={"weather_type": "rainy'; DROP TABLE runs;--"}).status_code
        == 422
    )


def test_literal_matches_the_database_enum() -> None:
    """The Literal must stay in step with the Postgres enum it validates.

    Reads the migration rather than restating the values, so adding a weather
    type in SQL without updating the Literal fails here instead of 500ing in
    production.
    """
    import re
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[2]
        / "supabase/migrations/20251119133437_initial_schema.sql"
    )
    sql = migration.read_text()
    match = re.search(r"CREATE TYPE weather_type AS ENUM \(([^)]+)\)", sql)
    assert match, "weather_type enum not found — did the migration move?"

    in_db = {v.strip().strip("'") for v in match.group(1).split(",")}
    assert in_db == set(WEATHER_TYPES), (
        f"drift: only in DB {in_db - set(WEATHER_TYPES)}, only in code {set(WEATHER_TYPES) - in_db}"
    )


def test_mapper_only_ever_produces_valid_enum_values() -> None:
    """Sync guard: a SmashRun mapping that emits a non-enum value would write a
    row Postgres rejects — the same class of bug, one layer upstream.
    """
    produced = {v for v in WEATHER_TYPE_MAP.values() if v is not None}
    assert produced <= set(WEATHER_TYPES), f"mapper emits unknown: {produced - set(WEATHER_TYPES)}"
