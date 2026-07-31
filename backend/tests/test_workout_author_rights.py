"""SB-486: who may change an athlete-scoped workout row.

Matthew builds and assigns; Gabe can log against a prescription and print it,
but not rewrite it. Whatever Gabe authors himself is his to edit, and Matthew as
coach can edit anything of his athlete's.

Hiding the buttons is not enforcement — without the route guard an athlete could
PATCH a coach's template straight through the API, so these cover the API rule
rather than the UI.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

COACH = uuid4()
ATHLETE_USER = uuid4()
ATHLETE_ID = uuid4()


def _template(created_by: UUID | None) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "name": "Upper Body Day",
        "type": "circuit",
        "rounds": 2,
        "user_id": str(COACH),
        "athlete_id": str(ATHLETE_ID),
        "created_by": str(created_by) if created_by else None,
        "items": [],
    }


def _patch_template(caller: UUID, existing: dict[str, Any], *, is_coach: bool) -> Any:
    """Call update_template with the repo and coach check stubbed."""
    repo = MagicMock()
    repo.get.return_value = existing
    repo.update.return_value = {**existing, "name": "Edited"}
    body = MagicMock()
    body.items = []
    body.model_dump.return_value = {"name": "Edited"}

    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.WorkoutTemplatesRepository", return_value=repo),
        patch("backend.routes.workouts.ExercisesRepository") as ex,
        patch("backend.routes.workouts.coaches_athlete", return_value=is_coach),
        patch("backend.routes.workouts.invalidate_user", new=_noop),
    ):
        ex.return_value.keys.return_value = set()
        from backend.routes.workouts import update_template

        return asyncio.run(
            update_template(
                template_id=UUID(existing["id"]),
                body=body,
                user_id=caller,
                athlete_id=ATHLETE_ID,
            )
        ), repo


async def _noop(*a: Any, **k: Any) -> None:
    return None


def test_coach_may_edit_their_athletes_template() -> None:
    result, repo = _patch_template(COACH, _template(COACH), is_coach=True)
    assert result.name == "Edited"
    repo.update.assert_called_once()


def test_athlete_may_not_edit_a_coachs_template() -> None:
    """The decided rule: Matthew's prescription stays authoritative."""
    with pytest.raises(HTTPException) as exc:
        _patch_template(ATHLETE_USER, _template(COACH), is_coach=False)

    assert exc.value.status_code == 403
    assert "not change it" in str(exc.value.detail)


def test_athlete_may_edit_their_own_template() -> None:
    result, repo = _patch_template(ATHLETE_USER, _template(ATHLETE_USER), is_coach=False)
    assert result.name == "Edited"
    repo.update.assert_called_once()


def test_null_created_by_is_treated_as_the_coachs() -> None:
    """Rows predating athlete authorship must not become athlete-editable."""
    with pytest.raises(HTTPException) as exc:
        _patch_template(ATHLETE_USER, _template(None), is_coach=False)
    assert exc.value.status_code == 403


def test_missing_template_is_404_not_403() -> None:
    """Don't leak the existence of another athlete's row through the new check."""
    repo = MagicMock()
    repo.get.return_value = None
    body = MagicMock()
    body.items = []

    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.WorkoutTemplatesRepository", return_value=repo),
        patch("backend.routes.workouts.ExercisesRepository") as ex,
        patch("backend.routes.workouts.coaches_athlete", return_value=False),
    ):
        ex.return_value.keys.return_value = set()
        from backend.routes.workouts import update_template

        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                update_template(
                    template_id=uuid4(), body=body, user_id=ATHLETE_USER, athlete_id=ATHLETE_ID
                )
            )

    assert exc.value.status_code == 404


# --- sessions: editable by their author, and by the coach for any -------------


def _delete_session(caller: UUID, existing: dict[str, Any] | None, *, is_coach: bool) -> Any:
    repo = MagicMock()
    repo.get.return_value = existing
    repo.delete.return_value = True

    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.WorkoutSessionsRepository", return_value=repo),
        patch("backend.routes.workouts.coaches_athlete", return_value=is_coach),
        patch("backend.routes.workouts.invalidate_user", new=_noop),
    ):
        from backend.routes.workouts import delete_session

        asyncio.run(delete_session(session_id=uuid4(), user_id=caller, athlete_id=ATHLETE_ID))
    return repo


def _session(created_by: UUID) -> dict[str, Any]:
    return {"id": str(uuid4()), "athlete_id": str(ATHLETE_ID), "created_by": str(created_by)}


def test_athlete_may_delete_the_session_they_logged() -> None:
    repo = _delete_session(ATHLETE_USER, _session(ATHLETE_USER), is_coach=False)
    repo.delete.assert_called_once()


def test_athlete_may_not_delete_a_session_the_coach_logged() -> None:
    with pytest.raises(HTTPException) as exc:
        _delete_session(ATHLETE_USER, _session(COACH), is_coach=False)
    assert exc.value.status_code == 403


def test_coach_may_delete_any_session_of_their_athlete() -> None:
    repo = _delete_session(COACH, _session(ATHLETE_USER), is_coach=True)
    repo.delete.assert_called_once()


# --- self-owned rows are untouched by any of this -----------------------------


def test_self_rows_skip_the_author_check() -> None:
    """A runner's own workouts have no athlete_id; _scope already limits them to
    the caller, so the new rule must not apply and must not need created_by."""
    from backend.routes.workouts import _require_may_modify

    _require_may_modify(ATHLETE_USER, None, {"created_by": None}, "workout")
