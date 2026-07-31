"""Name folding for the exercise catalog (SB-454).

These are the pure functions behind two things that have to agree: the search a
coach uses to find an existing movement, and the duplicate guard that stops them
creating a second row for it. ``scripts/audit_exercise_catalog.py`` imports the
same module, so a regression here surfaces in CI as a catalog blind spot too.
"""

import pytest

from src.shared.exercise_matching import (
    find_duplicate_candidates,
    matches_query,
    normalize,
    search_terms,
    squash,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Push-ups", "push up"),
        ("push ups", "push up"),
        ("Bent-over row", "bent over row"),
        ("bent over rows", "bent over row"),
        ("5-10-5 pro agility", "5 10 5 pro agility"),
        ("Farmer's carry", "farmer carry"),
        ("farmers carry", "farmer carry"),
        ("Bicep 90° hold", "bicep 90 hold"),
        ("Shoulder press", "shoulder press"),  # 'ss' keeps its s
        ("  Warm-up  ", "warm up"),
        ("step_up_max_jumps", "step up max jump"),
    ],
)
def test_normalize(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


def test_normalize_is_idempotent() -> None:
    """Both sides of every comparison are normalized, sometimes twice."""
    for raw in ("Farmer's carry", "Push-ups", "5-10-5 pro agility"):
        assert normalize(normalize(raw)) == normalize(raw)


def test_squash_drops_word_breaks() -> None:
    assert squash("Push-ups") == "pushup"
    assert squash("pushups") == "pushup"
    assert squash("Step-up max jumps") == "stepupmaxjump"


def test_search_terms_covers_name_and_aliases_in_both_forms() -> None:
    terms = search_terms({"display_name": "Push-ups", "aliases": ["press-up", ""]})
    assert terms == {"push up", "pushup", "press up", "pressup"}


@pytest.mark.parametrize(
    "query,display_name",
    [
        ("push ups", "Push-ups"),
        ("pushups", "Push-ups"),
        ("PUSH UPS", "Push-ups"),
        ("bent over row", "Bent-over row hold"),
        ("farmers carry", "Farmer's carry"),
        ("5 10 5", "5-10-5 pro agility"),
        ("warmup", "Warm-up"),
        ("cool down", "Cool-down"),
        ("step up max jump", "Step-up max jumps"),
        ("dynamic warm up drill", "Dynamic warm-up drills"),
    ],
)
def test_matches_query_folds_punctuation_and_plurals(query: str, display_name: str) -> None:
    """Every one of these was a blind spot the audit found in the live catalog."""
    assert matches_query(query, {"display_name": display_name, "aliases": []})


def test_matches_query_still_discriminates() -> None:
    row = {"display_name": "Push-ups", "aliases": []}
    assert not matches_query("squat", row)
    assert not matches_query("   ", row)
    assert not matches_query("", row)


def test_find_duplicate_candidates_is_exact_not_fuzzy() -> None:
    """Exact-normalized only. A fuzzy guard would block real variants, which is
    the whole reason the catalog has no unique-on-name constraint."""
    rows = [
        {"key": "pushups", "display_name": "Push-ups", "aliases": ["press-up"]},
        {"key": "plank", "display_name": "Plank", "aliases": []},
    ]
    assert [r["key"] for r in find_duplicate_candidates("push ups", [], rows)] == ["pushups"]
    assert [r["key"] for r in find_duplicate_candidates("Pushups", [], rows)] == ["pushups"]
    # an existing row's alias counts as that row's name
    assert [r["key"] for r in find_duplicate_candidates("Press-ups", [], rows)] == ["pushups"]
    # so does an incoming alias colliding
    assert [r["key"] for r in find_duplicate_candidates("Floor press", ["plank"], rows)] == [
        "plank"
    ]
    # real variants must remain creatable
    assert find_duplicate_candidates("Incline push-up", [], rows) == []
    assert find_duplicate_candidates("Side plank", [], rows) == []


def test_find_duplicate_candidates_with_nothing_to_match() -> None:
    rows = [{"key": "plank", "display_name": "Plank", "aliases": []}]
    assert find_duplicate_candidates("", None, rows) == []
    assert find_duplicate_candidates("Plank", None, []) == []
