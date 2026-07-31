"""SB-446: ranged targets render as ranges, and rest that isn't a number.

Matthew's 2026-07-30 speed-endurance block is "8-12x200 at 40-42 seconds" with
"60-90 second rest (go off how you feel)" and "full recovery" before the
ground-to-sprint accelerations. None of that fitted single scalars.
"""

from __future__ import annotations

from typing import Any

from cli.commands.workout import _fmt_range, _fmt_rest, _fmt_target, _range_status

LB = 0.453592


def _item(**over: Any) -> dict[str, Any]:
    return {"exercise_key": "pushups", "position": 0, **over}


class TestFmtRange:
    def test_two_bounds_render_as_a_range(self) -> None:
        assert _fmt_range(8, 12) == "8-12"

    def test_one_bound_renders_alone(self) -> None:
        assert _fmt_range(8, None) == "8"
        assert _fmt_range(None, 12) == "12"

    def test_equal_bounds_are_not_a_range(self) -> None:
        """ "10-10 reps" is a scalar wearing a costume."""
        assert _fmt_range(10, 10) == "10"

    def test_neither_bound_is_empty(self) -> None:
        assert _fmt_range(None, None) == ""

    def test_unit_is_appended_once(self) -> None:
        assert _fmt_range(60, 90, "s") == "60-90s"


class TestTargets:
    def test_rep_range(self) -> None:
        assert "8-12 reps" in _fmt_target(_item(target_reps=8, target_reps_max=12))

    def test_fixed_reps_unchanged(self) -> None:
        assert "15 reps" in _fmt_target(_item(target_reps=15))

    def test_load_range_round_trips_through_kg(self) -> None:
        """Prescribed "5-8lb dumbbells"; stored canonical kg must come back 5-8."""
        out = _fmt_target(_item(target_load_kg=5 * LB, target_load_max_kg=8 * LB))
        assert "5-8lb" in out

    def test_fixed_load_unchanged(self) -> None:
        assert "10lb" in _fmt_target(_item(target_load_kg=10 * LB))

    def test_duration_range_still_works(self) -> None:
        assert "40-42s" in _fmt_target(
            _item(target_duration_seconds=40, target_duration_max_seconds=42)
        )

    def test_the_speed_endurance_prescription(self) -> None:
        """8-12 x 200m at 40-42s, 60-90s rest by feel — one line, all of it."""
        out = _fmt_target(
            _item(
                exercise_key="interval_run",
                target_reps=8,
                target_reps_max=12,
                target_distance_m=200,
                target_duration_seconds=40,
                target_duration_max_seconds=42,
                rest_seconds=60,
                rest_seconds_max=90,
                rest_mode="autoregulated",
            )
        )
        assert "8-12 reps" in out
        assert "40-42s" in out
        assert "200m" in out
        assert "rest 60-90s (by feel)" in out

    def test_empty_item_renders_a_dash(self) -> None:
        assert _fmt_target(_item()) == "—"


class TestRest:
    def test_full_recovery_has_no_number(self) -> None:
        """Inventing seconds for "full recovery" would misreport the plan."""
        assert _fmt_rest(_item(rest_mode="full")) == "rest: full recovery"

    def test_full_recovery_wins_over_any_stored_number(self) -> None:
        assert _fmt_rest(_item(rest_mode="full", rest_seconds=60)) == "rest: full recovery"

    def test_autoregulated_without_numbers(self) -> None:
        assert _fmt_rest(_item(rest_mode="autoregulated")) == "rest: by feel"

    def test_autoregulated_range(self) -> None:
        assert (
            _fmt_rest(_item(rest_seconds=60, rest_seconds_max=90, rest_mode="autoregulated"))
            == "rest 60-90s (by feel)"
        )

    def test_fixed_rest(self) -> None:
        assert _fmt_rest(_item(rest_seconds=45)) == "rest 45s"

    def test_no_rest_prescribed(self) -> None:
        assert _fmt_rest(_item()) == ""


class TestRangeStatus:
    def test_inside_the_range_is_hit(self) -> None:
        assert "hit" in _range_status(10, 8, 12)

    def test_bounds_are_inclusive(self) -> None:
        assert "hit" in _range_status(8, 8, 12)
        assert "hit" in _range_status(12, 8, 12)

    def test_below_the_range(self) -> None:
        assert "under" in _range_status(6, 8, 12)

    def test_above_the_range_is_not_a_failure(self) -> None:
        """More reps than prescribed is over-delivery, not a miss."""
        assert "over" in _range_status(14, 8, 12)

    def test_lower_bound_only_means_more_is_fine(self) -> None:
        assert "hit" in _range_status(20, 15, None)
        assert "under" in _range_status(10, 15, None)

    def test_no_goal_grades_nothing(self) -> None:
        assert _range_status(10, None, None) == ""
