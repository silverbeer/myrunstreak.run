"""SB-367: GET /me/roles — granted roles plus the derived "athlete" entry.

admin/coach/runner are rows in ``user_roles``; "athlete" is derived from an
``athletes`` row pointing back at the caller, so the two are asserted
separately here.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4


@contextmanager
def _roles_env(*, roles: set[str], linked_athlete: dict[str, Any] | None = None) -> Any:
    roles_repo = MagicMock()
    roles_repo.list_roles.return_value = set(roles)
    athletes_repo = MagicMock()
    athletes_repo.get_by_linked_user.return_value = linked_athlete

    with (
        patch("backend.routes.athletes.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.athletes.UserRolesRepository", return_value=roles_repo),
        patch("backend.routes.athletes.AthletesRepository", return_value=athletes_repo),
    ):
        yield


def test_granted_roles_are_returned_sorted() -> None:
    from backend.routes.athletes import my_roles

    with _roles_env(roles={"runner", "coach"}):
        assert my_roles(user_id=uuid4()) == {"roles": ["coach", "runner"], "is_admin": False}


def test_a_user_can_hold_several_roles_at_once() -> None:
    """The point of the (user_id, role) PK: coach + runner is not a conflict."""
    from backend.routes.athletes import my_roles

    with _roles_env(roles={"admin", "coach", "runner"}):
        result = my_roles(user_id=uuid4())

    assert result["roles"] == ["admin", "coach", "runner"]
    assert result["is_admin"] is True


def test_no_roles_and_no_athlete_row_is_an_empty_list() -> None:
    from backend.routes.athletes import my_roles

    with _roles_env(roles=set()):
        assert my_roles(user_id=uuid4()) == {"roles": [], "is_admin": False}


def test_athlete_is_derived_from_the_linked_row() -> None:
    from backend.routes.athletes import my_roles

    with _roles_env(roles={"runner"}, linked_athlete={"id": str(uuid4())}):
        assert my_roles(user_id=uuid4())["roles"] == ["athlete", "runner"]


def test_athlete_without_a_coach_is_still_an_athlete() -> None:
    """Athlete-ness never consults coach_athletes — an uncoached athlete counts."""
    from backend.routes.athletes import my_roles

    with _roles_env(roles=set(), linked_athlete={"id": str(uuid4()), "linked_user_id": None}):
        assert my_roles(user_id=uuid4())["roles"] == ["athlete"]


def test_athlete_is_absent_when_no_row_links_back() -> None:
    from backend.routes.athletes import my_roles

    with _roles_env(roles={"coach"}, linked_athlete=None):
        assert "athlete" not in my_roles(user_id=uuid4())["roles"]


def test_derived_athlete_is_looked_up_for_the_caller() -> None:
    from backend.routes.athletes import my_roles

    uid = uuid4()
    athletes_repo = MagicMock()
    athletes_repo.get_by_linked_user.return_value = None
    roles_repo = MagicMock()
    roles_repo.list_roles.return_value = set()

    with (
        patch("backend.routes.athletes.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.athletes.UserRolesRepository", return_value=roles_repo),
        patch("backend.routes.athletes.AthletesRepository", return_value=athletes_repo),
    ):
        my_roles(user_id=uid)

    roles_repo.list_roles.assert_called_once_with(uid)
    athletes_repo.get_by_linked_user.assert_called_once_with(uid)


def test_granted_roles_set_is_not_mutated_by_the_derived_entry() -> None:
    """my_roles copies the repo's set — adding "athlete" must not leak back."""
    from backend.routes.athletes import my_roles

    granted = {"runner"}
    roles_repo = MagicMock()
    roles_repo.list_roles.return_value = granted
    athletes_repo = MagicMock()
    athletes_repo.get_by_linked_user.return_value = {"id": str(uuid4())}

    with (
        patch("backend.routes.athletes.get_supabase_client", return_value=MagicMock()),
        patch("backend.routes.athletes.UserRolesRepository", return_value=roles_repo),
        patch("backend.routes.athletes.AthletesRepository", return_value=athletes_repo),
    ):
        my_roles(user_id=uuid4())

    assert granted == {"runner"}
