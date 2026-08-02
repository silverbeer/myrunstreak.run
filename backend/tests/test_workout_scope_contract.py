"""The scope contract between the frontend and the workout API (SB-529).

Two regressions shipped on 2026-08-01 because nothing tested this seam:

* **SB-522** — the print view sent the string ``"undefined"`` as the athlete id.
  Frontend tests mocked ``apiCall`` entirely, so nothing saw it.
* **SB-524** — the fix omitted the header instead. Absence means "me", which
  routes ``_scope`` down the ``athlete_id IS NULL`` branch and cannot match a
  coach-assigned template, so the athlete got a 404. **The frontend tests
  asserted the header was absent** — they encoded the wrong behaviour and
  passed with confidence.

Both were invisible because the existing tests mock at the repository boundary
(``test_my_workouts.py`` asserts on ``templates_repo.list`` call args) and the
shared ``_FakeQuery`` in ``test_workout_repository.py`` ignores every filter —
``eq()`` and ``is_()`` just ``return self``. A wrong scope could not fail.

So this file does two things nothing else does:

1. runs the **real** ``_scope`` against a fake client that actually filters, and
2. drives the **real** route through ``TestClient`` so header parsing counts.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.shared.supabase_ops.workout_repository import WorkoutTemplatesRepository

# ---------------------------------------------------------------- filtering fake


class _FilteringQuery:
    """A fake query that HONOURS eq/is_, so a wrong scope actually returns nothing.

    The point of the exercise. The existing fake returns every row regardless of
    filter, which is why `_scope` has never been under test.
    """

    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows
        self._preds: list[Any] = []

    def select(self, *a: Any, **k: Any) -> _FilteringQuery:
        return self

    def eq(self, col: str, val: Any) -> _FilteringQuery:
        self._preds.append(lambda r: str(r.get(col)) == str(val))
        return self

    def is_(self, col: str, val: Any) -> _FilteringQuery:
        if str(val).lower() == "null":
            self._preds.append(lambda r: r.get(col) is None)
        return self

    def order(self, *a: Any, **k: Any) -> _FilteringQuery:
        return self

    def limit(self, *a: Any, **k: Any) -> _FilteringQuery:
        return self

    def range(self, *a: Any, **k: Any) -> _FilteringQuery:
        return self

    def in_(self, col: str, vals: Any) -> _FilteringQuery:
        wanted = {str(v) for v in vals}
        self._preds.append(lambda r: str(r.get(col)) in wanted)
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=[r for r in self._rows if all(p(r) for p in self._preds)])


class _FakeClient:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]):
        self.tables = tables

    def table(self, name: str) -> _FilteringQuery:
        return _FilteringQuery(self.tables.get(name, []))


COACH = uuid4()
ATHLETE_USER = uuid4()  # Gabe's auth user
ATHLETE_ROW = uuid4()  # his row in public.athletes — NOT the same id
TEMPLATE = uuid4()


def _tables() -> dict[str, list[dict[str, Any]]]:
    return {
        "workout_templates": [
            # Coach-assigned: owned by the coach, scoped to the athlete ROW.
            {
                "id": str(TEMPLATE),
                "user_id": str(COACH),
                "athlete_id": str(ATHLETE_ROW),
                "created_by": str(COACH),
                "name": "Monday At-Home (Matthew)",
                "type": "circuit",
                "rounds": 1,
                "source": "Matthew",
                "notes": None,
                "created_at": "2026-07-20T00:00:00+00:00",
            },
            # The coach's own unassigned template — must never leak to an athlete.
            {
                "id": str(uuid4()),
                "user_id": str(COACH),
                "athlete_id": None,
                "created_by": str(COACH),
                "name": "Coach private",
                "type": "circuit",
                "rounds": 1,
                "source": None,
                "notes": None,
                "created_at": "2026-07-20T00:00:00+00:00",
            },
        ],
        "template_items": [],
    }


# ---------------------------------------------------------------- the scope rule


def test_coach_assigned_template_needs_the_athlete_row_id() -> None:
    """The SB-524 regression, at the layer that actually decides it."""
    repo = WorkoutTemplatesRepository(_FakeClient(_tables()))  # type: ignore[arg-type]

    found = repo.get(ATHLETE_USER, TEMPLATE, athlete_id=ATHLETE_ROW)
    assert found is not None, "scoping by the athlete row must find the assigned template"
    assert found["name"] == "Monday At-Home (Matthew)"


def test_omitting_the_athlete_scope_cannot_find_it() -> None:
    """Absence means "my own self-authored rows", which this is not.

    This is precisely what SB-522's fix did, and why Gabe got "Template not
    found" instead of his workout.
    """
    repo = WorkoutTemplatesRepository(_FakeClient(_tables()))  # type: ignore[arg-type]
    assert repo.get(ATHLETE_USER, TEMPLATE, athlete_id=None) is None


def test_the_coachs_own_rows_never_leak_into_athlete_scope() -> None:
    """The other direction of the same rule — a coach's private template is theirs."""
    tables = _tables()
    private_id = UUID(tables["workout_templates"][1]["id"])
    repo = WorkoutTemplatesRepository(_FakeClient(tables))  # type: ignore[arg-type]

    assert repo.get(COACH, private_id, athlete_id=None) is not None
    assert repo.get(COACH, private_id, athlete_id=ATHLETE_ROW) is None


# ---------------------------------------------------------------- the HTTP seam


@pytest.fixture
def client() -> TestClient:
    """The real workouts router, with auth stubbed and access granted."""
    from backend.auth import authenticate_request
    from backend.routes import workouts

    app = FastAPI()
    app.include_router(workouts.router)
    app.dependency_overrides[authenticate_request] = lambda: ATHLETE_USER
    return TestClient(app, raise_server_exceptions=False)


def test_garbage_in_the_act_as_header_is_rejected(client: TestClient) -> None:
    """The SB-522 regression: the view sent the literal string "undefined".

    The header is typed ``UUID | None``, so FastAPI rejects it before any
    handler runs. A frontend-only test cannot see this at all.
    """
    r = client.get(
        f"/workouts/templates/{TEMPLATE}",
        headers={"X-Act-As-Athlete": "undefined"},
    )
    assert r.status_code == 422


def test_a_real_athlete_id_reaches_the_handler(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A well-formed id passes validation and is used as the scope."""
    from backend.routes import workouts

    monkeypatch.setattr(workouts, "require_athlete_access", lambda *_a, **_k: None)
    monkeypatch.setattr(workouts, "get_supabase_client", lambda: _FakeClient(_tables()))

    r = client.get(
        f"/workouts/templates/{TEMPLATE}",
        headers={"X-Act-As-Athlete": str(ATHLETE_ROW)},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Monday At-Home (Matthew)"


def test_no_header_404s_on_a_coach_assigned_template(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """End to end, the shape of the bug Gabe reported second."""
    from backend.routes import workouts

    monkeypatch.setattr(workouts, "get_supabase_client", lambda: _FakeClient(_tables()))

    r = client.get(f"/workouts/templates/{TEMPLATE}")
    assert r.status_code == 404
