"""SB-198: act-as scoping — acting_athlete dependency + athlete-owned rows."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from src.shared.supabase_ops.workout_repository import WorkoutTemplatesRepository


class _Q:
    def __init__(self, table: str, store: dict[str, list[dict[str, Any]]]) -> None:
        self.table, self.store = table, store
        self._mode, self._payload = "select", None

    def select(self, *a: Any, **k: Any) -> _Q:
        return self

    def eq(self, *a: Any, **k: Any) -> _Q:
        return self

    def is_(self, *a: Any, **k: Any) -> _Q:
        return self

    def order(self, *a: Any, **k: Any) -> _Q:
        return self

    def insert(self, payload: Any) -> _Q:
        self._mode, self._payload = "insert", payload
        return self

    def execute(self) -> Any:
        from types import SimpleNamespace

        if self._mode == "insert":
            rows = self._payload if isinstance(self._payload, list) else [self._payload]
            out = []
            for r in rows:
                row = dict(r) if "id" in r else {"id": str(uuid4()), **r}
                self.store.setdefault(self.table, []).append(row)
                out.append(row)
            return SimpleNamespace(data=out)
        return SimpleNamespace(data=self.store.get(self.table, []))


class _Client:
    def __init__(self) -> None:
        self.store: dict[str, list[dict[str, Any]]] = {}

    def table(self, name: str) -> _Q:
        return _Q(name, self.store)


def test_acting_athlete_none_when_no_header() -> None:
    from backend.routes.workouts import acting_athlete

    assert acting_athlete(user_id=uuid4(), x_act_as_athlete=None) is None


def test_acting_athlete_validates_and_returns() -> None:
    from backend.routes.workouts import acting_athlete

    coach, aid = uuid4(), uuid4()
    with patch("backend.routes.workouts.require_athlete_access") as guard:
        out = acting_athlete(user_id=coach, x_act_as_athlete=aid)
    assert out == aid
    guard.assert_called_once_with(coach, aid)


def test_acting_athlete_propagates_denial() -> None:
    from backend.routes.workouts import acting_athlete

    with patch(
        "backend.routes.workouts.require_athlete_access",
        side_effect=HTTPException(status_code=403, detail="no"),
    ):
        with pytest.raises(HTTPException) as exc:
            acting_athlete(user_id=uuid4(), x_act_as_athlete=uuid4())
    assert exc.value.status_code == 403


def test_template_create_with_athlete_sets_owner_fields() -> None:
    client = _Client()
    repo = WorkoutTemplatesRepository(client)  # type: ignore[arg-type]
    coach, aid = uuid4(), uuid4()

    repo.create(
        coach,
        {"name": "Saturday Circuit", "type": "circuit", "rounds": 3, "items": []},
        athlete_id=aid,
    )

    row = client.store["workout_templates"][0]
    assert row["athlete_id"] == str(aid)
    assert row["created_by"] == str(coach)
    assert row["user_id"] == str(coach)


def test_template_create_self_has_no_athlete() -> None:
    client = _Client()
    repo = WorkoutTemplatesRepository(client)  # type: ignore[arg-type]
    user = uuid4()

    repo.create(user, {"name": "My circuit", "type": "circuit", "rounds": 1, "items": []})

    row = client.store["workout_templates"][0]
    assert "athlete_id" not in row
    assert "created_by" not in row
    assert row["user_id"] == str(user)
