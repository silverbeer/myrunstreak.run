"""SB-332 / SB-578: GET /me/workouts.

An athlete (linked_user_id) sees the templates their coach assigned, scoped by
the athlete's own athlete_id — no coach act-as header involved.

Everyone else sees their OWN self-owned templates (athlete_id NULL). Returning
[] for a non-athlete made the training screens a dead end for any user a coach
had not created first (SB-578).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4


def _template_row(athlete_id, coach_id) -> dict:
    # A coach-created template: the row's user_id is the COACH, athlete_id the athlete.
    return {
        "id": str(uuid4()),
        "user_id": str(coach_id),
        "athlete_id": str(athlete_id),
        "created_by": str(coach_id),
        "name": "Monday At-Home",
        "type": "circuit",
        "rounds": 1,
        "source": "Matthew",
        "notes": None,
        "items": [],
        "created_at": "2026-07-20T00:00:00+00:00",
    }


def _patch(athletes_repo: MagicMock, templates_repo: MagicMock):
    return (
        patch("backend.routes.athletes.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.athletes.AthletesRepository", return_value=athletes_repo),
        patch("backend.routes.athletes.WorkoutTemplatesRepository", return_value=templates_repo),
    )


def test_linked_athlete_sees_assigned_templates() -> None:
    from backend.routes.athletes import my_workouts

    athlete_user, athlete_id, coach_id = uuid4(), uuid4(), uuid4()
    athletes_repo = MagicMock()
    athletes_repo.get_by_linked_user.return_value = {"id": str(athlete_id)}
    templates_repo = MagicMock()
    templates_repo.list.return_value = [_template_row(athlete_id, coach_id)]

    p1, p2, p3 = _patch(athletes_repo, templates_repo)
    with p1, p2, p3:
        out = my_workouts(user_id=athlete_user)

    assert len(out) == 1
    assert out[0].name == "Monday At-Home"
    assert out[0].source == "Matthew"
    # Scoped by the athlete's own athlete_id (coach-owned rows), not caller user_id.
    templates_repo.list.assert_called_once_with(athlete_user, athlete_id=athlete_id)


def _self_template_row(user_id) -> dict:
    # A self-owned template: user_id is the author, athlete_id is NULL.
    return {
        "id": str(uuid4()),
        "user_id": str(user_id),
        "athlete_id": None,
        "created_by": None,
        "name": "My Tuesday circuit",
        "type": "circuit",
        "rounds": 1,
        "source": None,
        "notes": None,
        "items": [],
        "created_at": "2026-08-04T00:00:00+00:00",
    }


def test_non_athlete_sees_their_own_templates() -> None:
    """SB-578: nobody's athlete still has plans of their own."""
    from backend.routes.athletes import my_workouts

    user_id = uuid4()
    athletes_repo = MagicMock()
    athletes_repo.get_by_linked_user.return_value = None
    templates_repo = MagicMock()
    templates_repo.list.return_value = [_self_template_row(user_id)]

    p1, p2, p3 = _patch(athletes_repo, templates_repo)
    with p1, p2, p3:
        out = my_workouts(user_id=user_id)

    assert len(out) == 1
    assert out[0].name == "My Tuesday circuit"
    # athlete_id=None is what scopes the query to self-owned rows.
    templates_repo.list.assert_called_once_with(user_id, athlete_id=None)


def test_non_athlete_with_nothing_gets_empty_list() -> None:
    from backend.routes.athletes import my_workouts

    athletes_repo = MagicMock()
    athletes_repo.get_by_linked_user.return_value = None
    templates_repo = MagicMock()
    templates_repo.list.return_value = []

    p1, p2, p3 = _patch(athletes_repo, templates_repo)
    with p1, p2, p3:
        out = my_workouts(user_id=uuid4())

    assert out == []
