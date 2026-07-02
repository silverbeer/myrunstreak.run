"""SB-219: athlete profile — field-level edit permissions + read redaction."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

ATHLETE_ROW = {
    "id": str(uuid4()),
    "display_name": "Kid",
    "birth_year": 2011,
    "linked_user_id": str(uuid4()),
    "created_by": str(uuid4()),
    "notes": None,
    "created_at": "2026-07-01T00:00:00+00:00",
}
PROFILE_ROW = {
    "sport": "soccer",
    "position": "midfield",
    "bio": "hi",
    "coaching_notes": "keep working on left foot",
    "updated_at": "2026-07-02T00:00:00+00:00",
}


@contextmanager
def _mock_athletes(*, coach: bool, repo: MagicMock):
    """Patch the athletes-route deps. `coach` toggles the coach/admin view."""
    coach_repo = MagicMock()
    coach_repo.active_link_exists.return_value = coach
    with (
        patch("backend.routes.athletes.require_athlete_access", return_value=None),
        patch("backend.routes.athletes.is_admin", return_value=False),
        patch("backend.routes.athletes.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.athletes.CoachAthletesRepository", return_value=coach_repo),
        patch("backend.routes.athletes.AthletesRepository", return_value=repo),
    ):
        yield


def _repo() -> MagicMock:
    r = MagicMock()
    r.get.return_value = ATHLETE_ROW
    r.get_profile.return_value = dict(PROFILE_ROW)
    return r


def test_coach_may_patch_any_field_including_coaching_notes() -> None:
    from backend.routes.athletes import update_athlete_profile
    from src.shared.models import AthleteProfileUpdate

    repo = _repo()
    with _mock_athletes(coach=True, repo=repo):
        out = update_athlete_profile(
            uuid4(),
            AthleteProfileUpdate(sport="soccer", coaching_notes="focus left foot"),
            user_id=uuid4(),
        )
    repo.upsert_profile.assert_called_once()
    sent = repo.upsert_profile.call_args.args[1]
    assert sent == {"sport": "soccer", "coaching_notes": "focus left foot"}
    # coach view keeps coaching_notes visible
    assert out.profile is not None and out.profile.coaching_notes == "keep working on left foot"


def test_athlete_may_patch_own_fields() -> None:
    from backend.routes.athletes import update_athlete_profile
    from src.shared.models import AthleteProfileUpdate

    repo = _repo()
    with _mock_athletes(coach=False, repo=repo):
        out = update_athlete_profile(
            uuid4(), AthleteProfileUpdate(bio="I love soccer"), user_id=uuid4()
        )
    repo.upsert_profile.assert_called_once()
    assert repo.upsert_profile.call_args.args[1] == {"bio": "I love soccer"}
    # athlete view redacts coaching_notes
    assert out.profile is not None and out.profile.coaching_notes is None


def test_athlete_patching_disallowed_field_is_403() -> None:
    from backend.routes.athletes import update_athlete_profile
    from src.shared.models import AthleteProfileUpdate

    repo = _repo()
    with _mock_athletes(coach=False, repo=repo):
        with pytest.raises(HTTPException) as exc:
            update_athlete_profile(uuid4(), AthleteProfileUpdate(sport="soccer"), user_id=uuid4())
    assert exc.value.status_code == 403
    repo.upsert_profile.assert_not_called()


def test_athlete_patching_coaching_notes_is_403() -> None:
    from backend.routes.athletes import update_athlete_profile
    from src.shared.models import AthleteProfileUpdate

    repo = _repo()
    with _mock_athletes(coach=False, repo=repo):
        with pytest.raises(HTTPException) as exc:
            update_athlete_profile(
                uuid4(), AthleteProfileUpdate(coaching_notes="hi"), user_id=uuid4()
            )
    assert exc.value.status_code == 403


def test_get_athlete_redacts_coaching_notes_for_athlete() -> None:
    from backend.routes.athletes import get_athlete

    repo = _repo()
    with _mock_athletes(coach=False, repo=repo):
        out = get_athlete(uuid4(), user_id=uuid4())
    assert out.profile is not None and out.profile.coaching_notes is None
    assert out.profile.sport == "soccer"  # non-private fields still present


def test_get_athlete_shows_coaching_notes_for_coach() -> None:
    from backend.routes.athletes import get_athlete

    repo = _repo()
    with _mock_athletes(coach=True, repo=repo):
        out = get_athlete(uuid4(), user_id=uuid4())
    assert out.profile is not None and out.profile.coaching_notes == "keep working on left foot"


def test_my_athlete_returns_none_when_unlinked() -> None:
    from backend.routes.athletes import my_athlete

    repo = MagicMock()
    repo.get_by_linked_user.return_value = None
    with _mock_athletes(coach=False, repo=repo):
        assert my_athlete(user_id=uuid4()) is None


def test_my_athlete_returns_profile_redacted() -> None:
    from backend.routes.athletes import my_athlete

    repo = _repo()
    repo.get_by_linked_user.return_value = ATHLETE_ROW
    with _mock_athletes(coach=False, repo=repo):
        out = my_athlete(user_id=uuid4())
    assert out is not None
    assert out.profile is not None and out.profile.coaching_notes is None
