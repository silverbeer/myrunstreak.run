"""Tests for the exercise catalog — repo logic + routes (SB-228 D1)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from src.shared.models.workout import ExerciseCreate, ExerciseUpdate
from src.shared.supabase_ops.workout_repository import ExercisesRepository, slugify

# --- pure logic --------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Goblet Squat", "goblet_squat"),
        ("40yd Dash!", "40yd_dash"),
        ("  Push-ups  ", "push_ups"),
        ("***", "exercise"),  # empty slug falls back
    ],
)
def test_slugify(name: str, expected: str) -> None:
    assert slugify(name) == expected


def test_unique_key_dedupes() -> None:
    repo = ExercisesRepository(MagicMock())
    repo.keys = MagicMock(return_value={"goblet_squat", "goblet_squat_2"})  # type: ignore[method-assign]
    assert repo._unique_key("Goblet Squat") == "goblet_squat_3"
    repo.keys = MagicMock(return_value=set())  # type: ignore[method-assign]
    assert repo._unique_key("Goblet Squat") == "goblet_squat"


def test_search_matches_name_and_aliases() -> None:
    repo = ExercisesRepository(MagicMock())
    repo.list_visible = MagicMock(  # type: ignore[method-assign]
        return_value=[
            {"key": "goblet_squat", "display_name": "Goblet Squat", "aliases": ["kb squat"]},
            {"key": "pushups", "display_name": "Push-ups", "aliases": ["press-up"]},
            {"key": "plank", "display_name": "Plank", "aliases": []},
        ]
    )
    uid = uuid4()
    assert [r["key"] for r in repo.search(uid, "goblet")] == ["goblet_squat"]
    assert [r["key"] for r in repo.search(uid, "press-up")] == ["pushups"]  # alias hit
    assert [r["key"] for r in repo.search(uid, "PLANK")] == ["plank"]  # case-insensitive
    assert repo.search(uid, "   ") == []  # blank → nothing


# --- routes ------------------------------------------------------------------


def _repo() -> MagicMock:
    return MagicMock()


def test_list_exercises_uses_list_visible() -> None:
    uid = uuid4()
    repo = _repo()
    repo.list_visible.return_value = [
        {"key": "pushups", "display_name": "Push-ups", "category": "strength"},
    ]
    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.ExercisesRepository", return_value=repo),
    ):
        from backend.routes.workouts import list_exercises

        result = list_exercises(user_id=uid)

    repo.list_visible.assert_called_once_with(uid)
    assert result[0].key == "pushups"


def test_create_exercise_returns_created() -> None:
    uid = uuid4()
    repo = _repo()
    repo.create.return_value = {
        "key": "goblet_squat",
        "display_name": "Goblet Squat",
        "category": "strength",
        "visibility": "private",
        "owner_id": str(uid),
    }
    repo.find_possible_duplicates.return_value = []
    body = ExerciseCreate(display_name="Goblet Squat", category="strength", measures=["reps"])
    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.ExercisesRepository", return_value=repo),
    ):
        from backend.routes.workouts import create_exercise

        result = create_exercise(body=body, user_id=uid)

    assert result.key == "goblet_squat"
    assert result.visibility == "private"
    # owner_id is not in the client payload — the repo sets it.
    assert "owner_id" not in repo.create.call_args.args[1]


def test_publish_exercise_404_when_not_owned() -> None:
    uid = uuid4()
    repo = _repo()
    repo.publish.return_value = None
    repo.get.return_value = None  # nothing to dup-check against
    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.ExercisesRepository", return_value=repo),
    ):
        from backend.routes.workouts import publish_exercise
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            publish_exercise(key="nope", user_id=uid)
    assert exc.value.status_code == 404


def test_update_exercise_patches_owned() -> None:
    uid = uuid4()
    repo = _repo()
    repo.update.return_value = {
        "key": "goblet_squat",
        "display_name": "Goblet Squat",
        "category": "strength",
        "cues": ["Chest up"],
    }
    body = ExerciseUpdate(cues=["Chest up"])
    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.is_admin", return_value=False),
        patch("backend.routes.workouts.ExercisesRepository", return_value=repo),
    ):
        from backend.routes.workouts import update_exercise

        result = update_exercise(key="goblet_squat", body=body, user_id=uid)

    assert result.cues == ["Chest up"]
    assert repo.update.call_args.args[2] == {"cues": ["Chest up"]}  # only patched field
    # A non-admin coach edits as owner-scoped.
    assert repo.update.call_args.kwargs["is_admin"] is False


def test_update_exercise_admin_patches_any() -> None:
    """An admin patches even a canonical (owner_id NULL) exercise — is_admin
    flows to the repo so the owner filter is dropped."""
    uid = uuid4()
    repo = _repo()
    repo.update.return_value = {
        "key": "pushups",
        "display_name": "Push-ups",
        "category": "strength",
        "cues": ["Elbows in"],
    }
    body = ExerciseUpdate(cues=["Elbows in"])
    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.is_admin", return_value=True),
        patch("backend.routes.workouts.ExercisesRepository", return_value=repo),
    ):
        from backend.routes.workouts import update_exercise

        result = update_exercise(key="pushups", body=body, user_id=uid)

    assert result.cues == ["Elbows in"]
    assert repo.update.call_args.kwargs["is_admin"] is True


def test_repo_update_admin_skips_owner_filter() -> None:
    """The repo drops the owner_id eq() when is_admin — verify via a spy query."""
    query = MagicMock()
    query.update.return_value = query
    query.eq.return_value = query
    query.execute.return_value = SimpleNamespace(data=[{"key": "pushups"}])
    supabase = MagicMock()
    supabase.table.return_value = query

    repo = ExercisesRepository(supabase)
    uid = uuid4()

    repo.update(uid, "pushups", {"cues": ["x"]}, is_admin=True)
    admin_eq_cols = [c.args[0] for c in query.eq.call_args_list]
    assert "owner_id" not in admin_eq_cols  # admin: no owner scoping

    query.eq.reset_mock()
    repo.update(uid, "pushups", {"cues": ["x"]}, is_admin=False)
    coach_eq_cols = [c.args[0] for c in query.eq.call_args_list]
    assert "owner_id" in coach_eq_cols  # coach: owner-scoped


def test_delete_exercise_404_when_not_owned() -> None:
    uid = uuid4()
    repo = _repo()
    repo.delete.return_value = False
    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.ExercisesRepository", return_value=repo),
    ):
        from backend.routes.workouts import delete_exercise
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            delete_exercise(key="nope", user_id=uid)
    assert exc.value.status_code == 404


# --- dedup guard: normalized matching + create/publish 409 (SB-454) -----------


def test_repo_search_finds_the_catalog_blind_spots() -> None:
    """The queries from the SB-454 audit, through the real repository path.

    The folding itself is unit-tested in ``tests/test_exercise_matching.py``;
    this covers `search` actually delegating to it, which is what regressed.
    """
    repo = ExercisesRepository(MagicMock())
    repo.list_visible = MagicMock(  # type: ignore[method-assign]
        return_value=[
            {"key": "pushups", "display_name": "Push-ups", "aliases": []},
            {"key": "row_hold", "display_name": "Bent-over row hold", "aliases": []},
            {"key": "farmers_carry", "display_name": "Farmer's carry", "aliases": []},
            {"key": "pro_agility", "display_name": "5-10-5 pro agility", "aliases": []},
        ]
    )
    uid = uuid4()
    assert [r["key"] for r in repo.search(uid, "push ups")] == ["pushups"]
    assert [r["key"] for r in repo.search(uid, "bent over row")] == ["row_hold"]
    assert [r["key"] for r in repo.search(uid, "farmers carry")] == ["farmers_carry"]
    assert [r["key"] for r in repo.search(uid, "5 10 5")] == ["pro_agility"]


def test_repo_find_possible_duplicates_public_only() -> None:
    repo = ExercisesRepository(MagicMock())
    repo.list_visible = MagicMock(  # type: ignore[method-assign]
        return_value=[
            {"key": "pushups", "display_name": "Push-ups", "aliases": [], "visibility": "public"},
            {"key": "pushup_2", "display_name": "Pushups", "aliases": [], "visibility": "private"},
        ]
    )
    uid = uuid4()
    assert len(repo.find_possible_duplicates(uid, "Push ups")) == 2
    public = repo.find_possible_duplicates(uid, "Push ups", public_only=True)
    assert [r["key"] for r in public] == ["pushups"]


def test_create_exercise_409_on_duplicate() -> None:
    uid = uuid4()
    repo = _repo()
    repo.find_possible_duplicates.return_value = [
        {"key": "pushups", "display_name": "Push-ups", "visibility": "public", "aliases": []}
    ]
    body = ExerciseCreate(display_name="Pushups", category="strength", measures=["reps"])
    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.ExercisesRepository", return_value=repo),
    ):
        from backend.routes.workouts import create_exercise
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            create_exercise(body=body, user_id=uid)

    assert exc.value.status_code == 409
    assert exc.value.detail["candidates"][0]["key"] == "pushups"
    repo.create.assert_not_called()


def test_create_exercise_force_bypasses_guard() -> None:
    uid = uuid4()
    repo = _repo()
    repo.create.return_value = {
        "key": "pushups_2",
        "display_name": "Pushups",
        "category": "strength",
        "visibility": "private",
    }
    body = ExerciseCreate(display_name="Pushups", category="strength", measures=["reps"])
    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.ExercisesRepository", return_value=repo),
    ):
        from backend.routes.workouts import create_exercise

        result = create_exercise(body=body, force=True, user_id=uid)

    assert result.key == "pushups_2"
    repo.find_possible_duplicates.assert_not_called()


def test_publish_exercise_409_when_public_library_has_it() -> None:
    uid = uuid4()
    repo = _repo()
    repo.get.return_value = {"key": "my_pushup", "display_name": "Pushups", "aliases": []}
    repo.find_possible_duplicates.return_value = [
        {"key": "pushups", "display_name": "Push-ups", "visibility": "public", "aliases": []}
    ]
    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.ExercisesRepository", return_value=repo),
    ):
        from backend.routes.workouts import publish_exercise
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            publish_exercise(key="my_pushup", user_id=uid)

    assert exc.value.status_code == 409
    assert repo.find_possible_duplicates.call_args.kwargs["public_only"] is True
    repo.publish.assert_not_called()


def test_publish_exercise_force_bypasses_guard() -> None:
    uid = uuid4()
    repo = _repo()
    repo.publish.return_value = {
        "key": "my_pushup",
        "display_name": "Pushups",
        "category": "strength",
        "visibility": "public",
    }
    with (
        patch("backend.routes.workouts.get_supabase_client"),
        patch("backend.routes.workouts.ExercisesRepository", return_value=repo),
    ):
        from backend.routes.workouts import publish_exercise

        result = publish_exercise(key="my_pushup", force=True, user_id=uid)

    assert result.visibility == "public"
    repo.find_possible_duplicates.assert_not_called()
