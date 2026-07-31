"""SB-483: the card and the debrief say which side.

Matthew's upper day lists side plank twice — right then left — and his lower day
does it for pistol squats and calf raises. Rendered without the variant, three
of twelve items are ambiguous pairs.
"""

from __future__ import annotations

from typing import Any

from cli.commands.workout import _fmt_name


def _item(key: str, **over: Any) -> dict[str, Any]:
    return {"exercise_key": key, "position": 0, **over}


def test_variant_is_shown() -> None:
    assert _fmt_name(_item("side_plank", variant="right")) == "side_plank (right)"


def test_both_sides_are_distinguishable() -> None:
    """The whole point — two entries of the same movement must not look alike."""
    right = _fmt_name(_item("side_plank", variant="right"))
    left = _fmt_name(_item("side_plank", variant="left"))
    assert right != left


def test_no_variant_renders_exactly_as_before() -> None:
    assert _fmt_name(_item("pushups")) == "pushups"


def test_empty_variant_is_not_rendered() -> None:
    """A blank string would print "pushups ()"."""
    assert _fmt_name(_item("pushups", variant="")) == "pushups"


def test_works_for_a_logged_set_too() -> None:
    """Review passes a set, not a template item — same shape, same helper."""
    st = {"exercise_key": "pistol_squat", "variant": "left", "reps": 8}
    assert _fmt_name(st) == "pistol_squat (left)"
