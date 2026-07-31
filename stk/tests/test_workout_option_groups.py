"""SB-448: "pick one of N" alternatives fold into a single block on the card.

Matthew's in-season aerobic day is run OR bike OR jump rope. Rendered flat, the
card told Gabe to do all three.
"""

from __future__ import annotations

from typing import Any

from cli.commands.workout import _group_options


def _item(key: str, position: int, **over: Any) -> dict[str, Any]:
    return {"exercise_key": key, "position": position, "section": "main", **over}


def test_mandatory_items_are_untouched() -> None:
    rows = _group_options([_item("pushups", 0), _item("plank", 1)])
    assert [r["kind"] for r in rows] == ["item", "item"]


def test_the_aerobic_day_folds_into_one_choice() -> None:
    rows = _group_options(
        [
            _item("dynamic_drills", 0),
            _item("easy_jog", 1, option_group="aerobic", option_group_label="Aerobic engine"),
            _item("bike", 2, option_group="aerobic"),
            _item("jump_rope", 3, option_group="aerobic"),
            _item("plank", 4),
        ]
    )

    assert [r["kind"] for r in rows] == ["item", "group", "item"]
    group = rows[1]
    assert group["label"] == "Aerobic engine"
    assert [i["exercise_key"] for i in group["items"]] == ["easy_jog", "bike", "jump_rope"]


def test_group_lands_at_its_first_member() -> None:
    rows = _group_options([_item("bike", 0, option_group="aerobic"), _item("plank", 1)])
    assert rows[0]["kind"] == "group"


def test_non_contiguous_alternatives_stay_one_block() -> None:
    """Repeating the heading would read as two separate choices."""
    rows = _group_options(
        [
            _item("easy_jog", 0, option_group="aerobic"),
            _item("plank", 1),
            _item("bike", 2, option_group="aerobic"),
        ]
    )

    assert [r["kind"] for r in rows] == ["group", "item"]
    assert len(rows[0]["items"]) == 2


def test_label_defaults_when_the_coach_did_not_write_one() -> None:
    rows = _group_options([_item("bike", 0, option_group="aerobic")])
    assert rows[0]["label"] == "Pick one"


def test_label_is_picked_up_from_a_later_member() -> None:
    rows = _group_options(
        [
            _item("bike", 0, option_group="aerobic"),
            _item("easy_jog", 1, option_group="aerobic", option_group_label="Aerobic engine"),
        ]
    )
    assert rows[0]["label"] == "Aerobic engine"


def test_distinct_groups_stay_distinct() -> None:
    rows = _group_options(
        [
            _item("easy_jog", 0, option_group="aerobic"),
            _item("pull_up", 1, option_group="upper"),
        ]
    )
    assert [r["kind"] for r in rows] == ["group", "group"]


def test_items_are_sorted_by_position() -> None:
    rows = _group_options([_item("plank", 2), _item("pushups", 1)])
    assert [r["item"]["exercise_key"] for r in rows] == ["pushups", "plank"]
