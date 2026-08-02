"""SB-536: a logged session can be called something, and renamed.

SB-531 opened the ad-hoc path; nothing named those sessions, so the Completed
list titled them on the session type and four workouts in a week read alike.

Naming is never required — a name field standing between the work and the credit
is friction in the wrong place — so the API takes it as optional and the client
supplies a default. Renaming afterwards follows the same rule as deleting: the
athlete owns what they logged, the coach owns their athlete's.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from src.shared.models.workout import WorkoutSessionCreate, WorkoutSessionUpdate

COACH = uuid4()
ATHLETE_USER = uuid4()
ATHLETE_ID = uuid4()


async def _noop(*a: Any, **k: Any) -> None:
    return None


def _row(created_by: UUID, name: str | None = None) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "user_id": str(COACH),
        "athlete_id": str(ATHLETE_ID),
        "created_by": str(created_by),
        "session_date": "2026-08-02",
        "name": name,
        "type": "circuit",
        "sets": [],
    }


def _patch_session(caller: UUID, existing: dict[str, Any], *, is_coach: bool, name: Any) -> Any:
    repo = MagicMock()
    repo.get.return_value = existing
    repo.update.side_effect = lambda user_id, sid, payload, athlete_id=None: {
        **existing,
        **payload,
    }

    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.WorkoutSessionsRepository", return_value=repo),
        patch("backend.routes.workouts.coaches_athlete", return_value=is_coach),
        patch("backend.routes.workouts.invalidate_user", new=_noop),
    ):
        from backend.routes.workouts import update_session

        return (
            asyncio.run(
                update_session(
                    session_id=UUID(existing["id"]),
                    body=WorkoutSessionUpdate(name=name),
                    user_id=caller,
                    athlete_id=ATHLETE_ID,
                )
            ),
            repo,
        )


def test_logging_a_session_never_requires_a_name() -> None:
    """The whole point of defaulting it: nothing stands between the work and the
    credit for it."""
    body = WorkoutSessionCreate(session_date="2026-08-02", type="circuit")
    assert body.name is None


def test_a_name_survives_the_create_payload() -> None:
    body = WorkoutSessionCreate(session_date="2026-08-02", type="circuit", name="Saturday 2 Aug")
    assert body.model_dump(mode="json")["name"] == "Saturday 2 Aug"


def test_an_athlete_may_rename_the_session_they_logged() -> None:
    result, repo = _patch_session(
        ATHLETE_USER, _row(ATHLETE_USER), is_coach=False, name="Garage circuit"
    )
    assert result.name == "Garage circuit"
    repo.update.assert_called_once()


def test_a_coach_may_rename_their_athletes_session() -> None:
    result, _ = _patch_session(COACH, _row(COACH), is_coach=True, name="Bike test")
    assert result.name == "Bike test"


def test_an_athlete_may_not_rename_a_session_their_coach_logged() -> None:
    """Hiding the control is not enforcement — Matthew's record of the session
    is not Gabe's to relabel."""
    with pytest.raises(HTTPException) as exc:
        _patch_session(ATHLETE_USER, _row(COACH), is_coach=False, name="mine now")

    assert exc.value.status_code == 403


def test_renaming_never_touches_what_was_logged() -> None:
    """The sets are the record; the name is a label on it."""
    _, repo = _patch_session(ATHLETE_USER, _row(ATHLETE_USER), is_coach=False, name="Sunday")
    payload = repo.update.call_args.args[2]
    assert payload == {"name": "Sunday"}


def test_clearing_the_name_is_a_real_edit() -> None:
    """Explicit null falls the row back to the template name / type, which is
    different from "not sent" — hence exclude_unset rather than exclude_none."""
    _, repo = _patch_session(ATHLETE_USER, _row(ATHLETE_USER, "Old"), is_coach=False, name=None)
    assert repo.update.call_args.args[2] == {"name": None}


def test_renaming_a_session_that_is_not_there_is_a_404() -> None:
    repo = MagicMock()
    repo.get.return_value = None

    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.WorkoutSessionsRepository", return_value=repo),
        patch("backend.routes.workouts.invalidate_user", new=_noop),
    ):
        from backend.routes.workouts import update_session

        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                update_session(
                    session_id=uuid4(),
                    body=WorkoutSessionUpdate(name="x"),
                    user_id=COACH,
                    athlete_id=ATHLETE_ID,
                )
            )

    assert exc.value.status_code == 404
    repo.update.assert_not_called()
