"""SB-332: athlete-facing GET /me/workouts.

An athlete (linked_user_id) sees the templates their coach assigned, scoped by
the athlete's own athlete_id — no coach act-as header involved.
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


def test_non_athlete_gets_empty_list() -> None:
    from backend.routes.athletes import my_workouts

    athletes_repo = MagicMock()
    athletes_repo.get_by_linked_user.return_value = None
    templates_repo = MagicMock()

    p1, p2, p3 = _patch(athletes_repo, templates_repo)
    with p1, p2, p3:
        out = my_workouts(user_id=uuid4())

    assert out == []
    templates_repo.list.assert_not_called()
