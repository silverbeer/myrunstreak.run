"""SB-534: putting a plan on a day, and who is allowed to.

Either side may schedule — Matthew assigning Thursday, or Gabe planning his own
week — and every row remembers which of them it was, because the athlete's
screen has to say so without being told.

Removal follows the same split as every other athlete-scoped row (SB-486): a
coach may clear anything on their athlete's calendar; the athlete may clear what
they put there themselves, and not the workout their coach expects of them.

The athlete path is covered explicitly here. Three bugs shipped in one week on
routes only an athlete takes, every one of them fixtured as the coach.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from src.shared.models.workout import WorkoutScheduleCreate

COACH = uuid4()
ATHLETE_USER = uuid4()
ATHLETE_ID = uuid4()
TEMPLATE_ID = uuid4()


async def _noop(*a: Any, **k: Any) -> None:
    return None


def _row(created_by: UUID) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "user_id": str(COACH),
        "athlete_id": str(ATHLETE_ID),
        "created_by": str(created_by),
        "template_id": str(TEMPLATE_ID),
        "scheduled_for": "2026-08-06",
        "notes": None,
    }


def _create(caller: UUID, *, template_found: bool = True) -> Any:
    """Call create_schedule with the repositories stubbed."""
    sched = MagicMock()
    sched.create.side_effect = lambda user_id, payload, athlete_id=None: {
        **_row(user_id),
        **payload,
    }
    templates = MagicMock()
    templates.get.return_value = {"id": str(TEMPLATE_ID)} if template_found else None

    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.WorkoutScheduleRepository", return_value=sched),
        patch("backend.routes.workouts.WorkoutTemplatesRepository", return_value=templates),
        patch("backend.routes.workouts.invalidate_user", new=_noop),
    ):
        from backend.routes.workouts import create_schedule

        return (
            asyncio.run(
                create_schedule(
                    body=WorkoutScheduleCreate(
                        template_id=TEMPLATE_ID, scheduled_for=date(2026, 8, 6)
                    ),
                    user_id=caller,
                    athlete_id=ATHLETE_ID,
                )
            ),
            sched,
        )


def _delete(caller: UUID, existing: dict[str, Any], *, is_coach: bool) -> Any:
    repo = MagicMock()
    repo.get.return_value = existing
    repo.delete.return_value = True

    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.WorkoutScheduleRepository", return_value=repo),
        patch("backend.routes.workouts.coaches_athlete", return_value=is_coach),
        patch("backend.routes.workouts.invalidate_user", new=_noop),
    ):
        from backend.routes.workouts import delete_schedule

        asyncio.run(
            delete_schedule(schedule_id=UUID(existing["id"]), user_id=caller, athlete_id=ATHLETE_ID)
        )
        return repo


def test_a_coach_can_schedule_a_workout_for_their_athlete() -> None:
    result, repo = _create(COACH)
    assert result.scheduled_for == date(2026, 8, 6)
    repo.create.assert_called_once()


def test_an_athlete_can_schedule_their_own_week() -> None:
    """The decision this ticket records: scheduling is not a coach-only verb."""
    result, _ = _create(ATHLETE_USER)
    assert result.scheduled_for == date(2026, 8, 6)


def test_the_row_records_who_scheduled_it() -> None:
    """The whole reason this is a table and not a date column on the template."""
    by_coach, _ = _create(COACH)
    by_athlete, _ = _create(ATHLETE_USER)

    assert by_coach.created_by == COACH
    assert by_athlete.created_by == ATHLETE_USER


def test_scheduling_a_template_you_cannot_see_is_a_404() -> None:
    """Scheduling an invisible template would leak that it exists, and leave a
    row that renders as a blank card."""
    with pytest.raises(HTTPException) as exc:
        _create(COACH, template_found=False)

    assert exc.value.status_code == 404


def test_a_coach_may_unschedule_anything_of_their_athletes() -> None:
    repo = _delete(COACH, _row(COACH), is_coach=True)
    repo.delete.assert_called_once()


def test_an_athlete_may_unschedule_what_they_scheduled() -> None:
    repo = _delete(ATHLETE_USER, _row(ATHLETE_USER), is_coach=False)
    repo.delete.assert_called_once()


def test_an_athlete_may_not_unschedule_what_their_coach_assigned() -> None:
    """Matthew's Thursday is not Gabe's to delete — hiding the button is not
    enforcement."""
    with pytest.raises(HTTPException) as exc:
        _delete(ATHLETE_USER, _row(COACH), is_coach=False)

    assert exc.value.status_code == 403


def test_unscheduling_something_that_is_not_there_is_a_404() -> None:
    repo = MagicMock()
    repo.get.return_value = None

    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.WorkoutScheduleRepository", return_value=repo),
        patch("backend.routes.workouts.invalidate_user", new=_noop),
    ):
        from backend.routes.workouts import delete_schedule

        with pytest.raises(HTTPException) as exc:
            asyncio.run(delete_schedule(schedule_id=uuid4(), user_id=COACH, athlete_id=ATHLETE_ID))

    assert exc.value.status_code == 404
    repo.delete.assert_not_called()
