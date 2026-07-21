"""SB-195: coach platform foundation — roles, athlete access, routes."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException


@contextmanager
def _admin_env(
    *,
    roles: set[str] | None = None,
    athlete: dict[str, Any] | None = None,
    active_link: bool = False,
    admin_ids: set[str] | None = None,
) -> Any:
    """Patch backend.admin's dependencies for access-logic tests."""
    roles_repo = MagicMock()
    roles_repo.has_role.side_effect = lambda _uid, role: role in (roles or set())
    athletes_repo = MagicMock()
    athletes_repo.get.return_value = athlete
    links_repo = MagicMock()
    links_repo.active_link_exists.return_value = active_link
    settings = SimpleNamespace(admin_ids=lambda: admin_ids or set())

    with (
        patch("backend.admin.get_supabase_client", return_value=MagicMock()),
        patch("backend.admin.UserRolesRepository", return_value=roles_repo),
        patch("backend.admin.AthletesRepository", return_value=athletes_repo),
        patch("backend.admin.CoachAthletesRepository", return_value=links_repo),
        patch("backend.admin.get_settings", return_value=settings),
    ):
        yield


def test_require_admin_db_role() -> None:
    from backend.admin import require_admin

    with _admin_env(roles={"admin"}):
        require_admin(uuid4())  # no raise


def test_require_admin_config_fallback() -> None:
    from backend.admin import require_admin

    uid = uuid4()
    with _admin_env(admin_ids={str(uid).lower()}):
        require_admin(uid)  # legacy allowlist still works


def test_require_admin_denies() -> None:
    from backend.admin import require_admin

    with _admin_env():
        with pytest.raises(HTTPException) as exc:
            require_admin(uuid4())
    assert exc.value.status_code == 403


def test_require_coach_allows_admin_and_coach() -> None:
    from backend.admin import require_coach

    with _admin_env(roles={"coach"}):
        require_coach(uuid4())
    with _admin_env(roles={"admin"}):
        require_coach(uuid4())  # admins are coaches too
    with _admin_env():
        with pytest.raises(HTTPException):
            require_coach(uuid4())


def test_can_access_athlete_self() -> None:
    from backend.admin import can_access_athlete

    uid = uuid4()
    athlete = {"id": str(uuid4()), "linked_user_id": str(uid)}
    with _admin_env(athlete=athlete):
        assert can_access_athlete(uid, uuid4()) is True


def test_can_access_athlete_active_coach() -> None:
    from backend.admin import can_access_athlete

    athlete = {"id": str(uuid4()), "linked_user_id": None}
    with _admin_env(athlete=athlete, active_link=True):
        assert can_access_athlete(uuid4(), uuid4()) is True


def test_can_access_athlete_admin() -> None:
    from backend.admin import can_access_athlete

    athlete = {"id": str(uuid4()), "linked_user_id": None}
    with _admin_env(athlete=athlete, active_link=False, roles={"admin"}):
        assert can_access_athlete(uuid4(), uuid4()) is True


def test_can_access_athlete_denied() -> None:
    from backend.admin import can_access_athlete

    athlete = {"id": str(uuid4()), "linked_user_id": None}
    with _admin_env(athlete=athlete, active_link=False):
        assert can_access_athlete(uuid4(), uuid4()) is False


def test_can_access_athlete_missing_is_false() -> None:
    from backend.admin import can_access_athlete

    with _admin_env(athlete=None):
        assert can_access_athlete(uuid4(), uuid4()) is False


def test_create_athlete_requires_coach() -> None:
    from backend.routes.athletes import create_athlete
    from src.shared.models import AthleteCreate

    with _admin_env():  # not a coach
        with pytest.raises(HTTPException) as exc:
            create_athlete(AthleteCreate(display_name="Gabe"), user_id=uuid4())
    assert exc.value.status_code == 403


def test_create_athlete_creates_and_self_assigns() -> None:
    from backend.routes.athletes import create_athlete
    from src.shared.models import AthleteCreate

    coach = uuid4()
    aid = uuid4()
    athletes_repo = MagicMock()
    athletes_repo.create.return_value = {
        "id": str(aid),
        "display_name": "Gabe",
        "birth_year": 2011,
        "linked_user_id": None,
        "created_by": str(coach),
        "notes": None,
        "created_at": "2026-06-21T00:00:00+00:00",
    }
    links_repo = MagicMock()

    with (
        _admin_env(roles={"coach"}),
        patch("backend.routes.athletes.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.athletes.AthletesRepository", return_value=athletes_repo),
        patch("backend.routes.athletes.CoachAthletesRepository", return_value=links_repo),
    ):
        out = create_athlete(AthleteCreate(display_name="Gabe", birth_year=2011), user_id=coach)

    assert out.display_name == "Gabe"
    links_repo.assign.assert_called_once_with(coach, aid)


def test_assign_coach_grants_role_and_links() -> None:
    from backend.routes.athletes import AssignCoachRequest, assign_coach

    caller = uuid4()
    new_coach = uuid4()
    aid = uuid4()
    roles_repo = MagicMock()
    links_repo = MagicMock()
    links_repo.assign.return_value = {
        "id": str(uuid4()),
        "coach_id": str(new_coach),
        "athlete_id": str(aid),
        "status": "active",
        "started_at": "2026-06-21T00:00:00+00:00",
        "ended_at": None,
        "created_at": "2026-06-21T00:00:00+00:00",
    }

    with (
        _admin_env(roles={"admin"}, athlete={"id": str(aid), "linked_user_id": None}),
        patch("backend.routes.athletes.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.athletes.UserRolesRepository", return_value=roles_repo),
        patch("backend.routes.athletes.CoachAthletesRepository", return_value=links_repo),
    ):
        out = assign_coach(aid, AssignCoachRequest(coach_id=new_coach), user_id=caller)

    roles_repo.grant.assert_called_once_with(new_coach, "coach")
    assert str(out.coach_id) == str(new_coach)


def test_assign_coach_by_email_resolves_user() -> None:
    from backend.routes.athletes import AssignCoachRequest, assign_coach

    aid = uuid4()
    coach_uid = uuid4()
    users_repo = MagicMock()
    users_repo.get_user_by_email.return_value = {"user_id": str(coach_uid)}
    roles_repo = MagicMock()
    links_repo = MagicMock()
    links_repo.assign.return_value = {
        "id": str(uuid4()),
        "coach_id": str(coach_uid),
        "athlete_id": str(aid),
        "status": "active",
        "started_at": "2026-06-21T00:00:00+00:00",
        "ended_at": None,
        "created_at": "2026-06-21T00:00:00+00:00",
    }

    with (
        _admin_env(roles={"admin"}, athlete={"id": str(aid), "linked_user_id": None}),
        patch("backend.routes.athletes.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.athletes.UsersRepository", return_value=users_repo),
        patch("backend.routes.athletes.UserRolesRepository", return_value=roles_repo),
        patch("backend.routes.athletes.CoachAthletesRepository", return_value=links_repo),
    ):
        out = assign_coach(
            aid, AssignCoachRequest(coach_email="matthew@example.com"), user_id=uuid4()
        )

    users_repo.get_user_by_email.assert_called_once_with("matthew@example.com")
    roles_repo.grant.assert_called_once_with(coach_uid, "coach")
    assert str(out.coach_id) == str(coach_uid)


def test_assign_coach_by_email_unknown_404() -> None:
    from backend.routes.athletes import AssignCoachRequest, assign_coach

    aid = uuid4()
    users_repo = MagicMock()
    users_repo.get_user_by_email.return_value = None

    with (
        _admin_env(roles={"admin"}, athlete={"id": str(aid), "linked_user_id": None}),
        patch("backend.routes.athletes.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.athletes.UsersRepository", return_value=users_repo),
    ):
        with pytest.raises(HTTPException) as exc:
            assign_coach(aid, AssignCoachRequest(coach_email="nobody@example.com"), user_id=uuid4())
    assert exc.value.status_code == 404


def test_assign_coach_request_requires_id_or_email() -> None:
    from backend.routes.athletes import AssignCoachRequest

    with pytest.raises(ValueError):
        AssignCoachRequest()


def test_list_coaches_enriches_with_name_and_email() -> None:
    """SB-272: each coach link carries the coach's display name + email for the UI."""
    from backend.routes.athletes import list_coaches

    aid = uuid4()
    coach_a, coach_b = uuid4(), uuid4()
    links_repo = MagicMock()
    links_repo.list_active_for_athlete.return_value = [
        {
            "id": str(uuid4()),
            "coach_id": str(coach_a),
            "athlete_id": str(aid),
            "status": "active",
            "started_at": "2026-07-02T00:00:00+00:00",
            "ended_at": None,
            "created_at": "2026-07-02T00:00:00+00:00",
        },
        {
            "id": str(uuid4()),
            "coach_id": str(coach_b),
            "athlete_id": str(aid),
            "status": "active",
            "started_at": "2026-07-13T00:00:00+00:00",
            "ended_at": None,
            "created_at": "2026-07-13T00:00:00+00:00",
        },
    ]
    users_repo = MagicMock()
    users_repo.get_user_by_id.side_effect = lambda cid: {
        str(coach_a): {"display_name": "Tom", "email": "tom@example.com"},
        str(coach_b): {"display_name": "Matthew", "email": "matthew@example.com"},
    }[str(cid)]

    with (
        _admin_env(roles={"admin"}, athlete={"id": str(aid), "linked_user_id": None}),
        patch("backend.routes.athletes.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.athletes.CoachAthletesRepository", return_value=links_repo),
        patch("backend.routes.athletes.UsersRepository", return_value=users_repo),
    ):
        out = list_coaches(aid, user_id=uuid4())

    assert [c.coach_display_name for c in out] == ["Tom", "Matthew"]
    assert [c.coach_email for c in out] == ["tom@example.com", "matthew@example.com"]


def test_list_coaches_tolerates_missing_user() -> None:
    """A coach link whose user row can't be resolved still returns (name/email None)."""
    from backend.routes.athletes import list_coaches

    aid, coach = uuid4(), uuid4()
    links_repo = MagicMock()
    links_repo.list_active_for_athlete.return_value = [
        {
            "id": str(uuid4()),
            "coach_id": str(coach),
            "athlete_id": str(aid),
            "status": "active",
            "started_at": "2026-07-13T00:00:00+00:00",
            "ended_at": None,
            "created_at": "2026-07-13T00:00:00+00:00",
        }
    ]
    users_repo = MagicMock()
    users_repo.get_user_by_id.return_value = None

    with (
        _admin_env(roles={"admin"}, athlete={"id": str(aid), "linked_user_id": None}),
        patch("backend.routes.athletes.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.athletes.CoachAthletesRepository", return_value=links_repo),
        patch("backend.routes.athletes.UsersRepository", return_value=users_repo),
    ):
        out = list_coaches(aid, user_id=uuid4())

    assert len(out) == 1
    assert out[0].coach_display_name is None
    assert out[0].coach_email is None


class _FakeCoachLinks:
    """Minimal Supabase table double for CoachAthletesRepository.assign (SB-271).

    Records whether an INSERT happened and returns a preset row for the active
    lookup, so the test can assert the idempotent no-op path.
    """

    def __init__(self, existing: list[dict[str, Any]]):
        self._existing = existing
        self._mode = "select"
        self.inserted = False

    def table(self, _name: str) -> _FakeCoachLinks:
        self._mode = "select"
        return self

    def select(self, *a: Any, **k: Any) -> _FakeCoachLinks:
        self._mode = "select"
        return self

    def eq(self, *a: Any, **k: Any) -> _FakeCoachLinks:
        return self

    def insert(self, payload: Any) -> _FakeCoachLinks:
        self._mode = "insert"
        self.inserted = True
        self._payload = payload
        return self

    def execute(self) -> Any:
        if self._mode == "select":
            return SimpleNamespace(data=list(self._existing))
        row = {
            "id": str(uuid4()),
            "status": "active",
            "started_at": "2026-07-13T00:00:00+00:00",
            "ended_at": None,
            "created_at": "2026-07-13T00:00:00+00:00",
            **self._payload,
        }
        return SimpleNamespace(data=[row])


def test_assign_returns_existing_active_link_without_insert() -> None:
    """SB-271: re-adding an already-active coach is a no-op, not a duplicate INSERT."""
    from src.shared.supabase_ops.athletes_repository import CoachAthletesRepository

    coach, aid = uuid4(), uuid4()
    existing = {
        "id": str(uuid4()),
        "coach_id": str(coach),
        "athlete_id": str(aid),
        "status": "active",
        "started_at": "2026-07-02T00:00:00+00:00",
        "ended_at": None,
        "created_at": "2026-07-02T00:00:00+00:00",
    }
    fake = _FakeCoachLinks(existing=[existing])
    out = CoachAthletesRepository(fake).assign(coach, aid)  # type: ignore[arg-type]

    assert fake.inserted is False
    assert out == existing


def test_assign_inserts_when_no_active_link() -> None:
    from src.shared.supabase_ops.athletes_repository import CoachAthletesRepository

    coach, aid = uuid4(), uuid4()
    fake = _FakeCoachLinks(existing=[])
    out = CoachAthletesRepository(fake).assign(coach, aid)  # type: ignore[arg-type]

    assert fake.inserted is True
    assert out["coach_id"] == str(coach)
    assert out["athlete_id"] == str(aid)
    assert out["status"] == "active"
