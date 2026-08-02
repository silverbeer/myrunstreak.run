"""SB-535: who may set a week that repeats, and what turning it off means.

Recurrence follows one-off scheduling exactly (SB-534): either side may set a
pattern, the rule records which of them did, and only its author — or the coach,
for their athlete — may change it. Repeating is not a coach-only verb, for the
same reason scheduling is not.

The athlete path is covered explicitly; it is the surface where the bugs land.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from src.shared.models.workout import WorkoutRecurrenceCreate, WorkoutRecurrenceUpdate

COACH = uuid4()
ATHLETE_USER = uuid4()
ATHLETE_ID = uuid4()
TEMPLATE_ID = uuid4()


async def _noop(*a: Any, **k: Any) -> None:
    return None


def _row(created_by: UUID, **over: Any) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "user_id": str(COACH),
        "athlete_id": str(ATHLETE_ID),
        "created_by": str(created_by),
        "template_id": str(TEMPLATE_ID),
        "byweekday": [1, 4],
        "starts_on": "2026-08-03",
        "ends_on": None,
        "active": True,
        "generated_through": None,
        **over,
    }


def _create(
    caller: UUID, *, template_found: bool = True, byweekday: list[int] | None = None
) -> Any:
    repo = MagicMock()
    repo.create.side_effect = lambda user_id, payload, athlete_id=None: {
        **_row(user_id),
        **payload,
    }
    templates = MagicMock()
    templates.get.return_value = {"id": str(TEMPLATE_ID)} if template_found else None

    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.WorkoutRecurrenceRepository", return_value=repo),
        patch("backend.routes.workouts.WorkoutTemplatesRepository", return_value=templates),
        patch("backend.routes.workouts.invalidate_user", new=_noop),
    ):
        from backend.routes.workouts import create_recurrence

        return (
            asyncio.run(
                create_recurrence(
                    body=WorkoutRecurrenceCreate(
                        template_id=TEMPLATE_ID,
                        byweekday=byweekday or [1, 4],
                        starts_on=date(2026, 8, 3),
                    ),
                    user_id=caller,
                    athlete_id=ATHLETE_ID,
                )
            ),
            repo,
        )


def _patch(caller: UUID, existing: dict[str, Any], *, is_coach: bool, **fields: Any) -> Any:
    repo = MagicMock()
    repo.get.return_value = existing
    repo.update.side_effect = lambda user_id, rid, payload, athlete_id=None: {
        **existing,
        **payload,
    }

    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.WorkoutRecurrenceRepository", return_value=repo),
        patch("backend.routes.workouts.coaches_athlete", return_value=is_coach),
        patch("backend.routes.workouts.invalidate_user", new=_noop),
    ):
        from backend.routes.workouts import update_recurrence

        return (
            asyncio.run(
                update_recurrence(
                    recurrence_id=UUID(existing["id"]),
                    body=WorkoutRecurrenceUpdate(**fields),
                    user_id=caller,
                    athlete_id=ATHLETE_ID,
                )
            ),
            repo,
        )


def test_a_coach_can_set_the_week_that_repeats() -> None:
    result, repo = _create(COACH)
    assert result.byweekday == [1, 4]
    repo.create.assert_called_once()


def test_an_athlete_can_repeat_something_of_their_own() -> None:
    """Consistency with SB-534: if scheduling is not coach-only, repeating is
    not either."""
    result, _ = _create(ATHLETE_USER)
    assert result.created_by == ATHLETE_USER


def test_creating_a_pattern_generates_its_first_occasions_immediately() -> None:
    """Otherwise the repeat is invisible until something else reads the
    schedule, which reads as it not having worked."""
    _, repo = _create(COACH)
    repo.materialise.assert_called_once()


def test_repeating_a_template_you_cannot_see_is_a_404() -> None:
    with pytest.raises(HTTPException) as exc:
        _create(COACH, template_found=False)

    assert exc.value.status_code == 404


def test_weekdays_are_validated_and_normalised() -> None:
    """0 = Sunday .. 6 = Saturday. Duplicates collapse and the order is fixed,
    so two ways of saying the same week store identically."""
    body = WorkoutRecurrenceCreate(
        template_id=TEMPLATE_ID, byweekday=[4, 1, 4], starts_on=date(2026, 8, 3)
    )
    assert body.byweekday == [1, 4]

    with pytest.raises(ValueError):
        WorkoutRecurrenceCreate(template_id=TEMPLATE_ID, byweekday=[7], starts_on=date(2026, 8, 3))
    with pytest.raises(ValueError):
        WorkoutRecurrenceCreate(template_id=TEMPLATE_ID, byweekday=[], starts_on=date(2026, 8, 3))


def test_turning_a_pattern_off_is_a_patch_not_a_delete() -> None:
    """Stops future occasions; everything already generated — and anything
    logged against it — is left alone."""
    result, repo = _patch(ATHLETE_USER, _row(ATHLETE_USER), is_coach=False, active=False)
    assert result.active is False
    assert repo.update.call_args.args[2] == {"active": False}


def test_a_coach_may_change_their_athletes_pattern() -> None:
    result, _ = _patch(COACH, _row(COACH), is_coach=True, byweekday=[2])
    assert result.byweekday == [2]


def test_an_athlete_may_not_change_a_pattern_their_coach_set() -> None:
    """Matthew's in-season week is not Gabe's to rewrite."""
    with pytest.raises(HTTPException) as exc:
        _patch(ATHLETE_USER, _row(COACH), is_coach=False, active=False)

    assert exc.value.status_code == 403


def test_deleting_a_pattern_leaves_what_it_already_generated() -> None:
    """Those occasions are on the calendar; removing the rule is not a claim
    that the next two weeks never happened."""
    repo = MagicMock()
    existing = _row(ATHLETE_USER)
    repo.get.return_value = existing
    repo.delete.return_value = True

    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.WorkoutRecurrenceRepository", return_value=repo),
        patch("backend.routes.workouts.coaches_athlete", return_value=False),
        patch("backend.routes.workouts.invalidate_user", new=_noop),
    ):
        from backend.routes.workouts import delete_recurrence

        asyncio.run(
            delete_recurrence(
                recurrence_id=UUID(existing["id"]), user_id=ATHLETE_USER, athlete_id=ATHLETE_ID
            )
        )

    repo.delete.assert_called_once()
    # No schedule rows are touched here — the FK goes null on its own.
    assert "workout_schedule" not in str(repo.mock_calls)


def test_reading_the_schedule_generates_what_is_owed_first() -> None:
    """Coming up fills by being read, rather than by a cron job somebody has to
    remember exists."""
    sched = MagicMock()
    sched.list.return_value = []
    rec = MagicMock()

    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.WorkoutScheduleRepository", return_value=sched),
        patch("backend.routes.workouts.WorkoutRecurrenceRepository", return_value=rec),
    ):
        from backend.routes.workouts import list_schedule

        list_schedule(user_id=ATHLETE_USER, athlete_id=ATHLETE_ID)

    rec.materialise.assert_called_once()
    sched.list.assert_called_once()
