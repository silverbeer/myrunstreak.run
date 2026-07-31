"""SB-447: heart rate, cadence and speed on the card and in review.

The 2026-07-30 plan is the first to prescribe them — bike intervals at HR
160-175, the in-season aerobic day at HR 120-145 — and the coach asked for the
instrumentation directly: "insert as many metrics as you can".
"""

from __future__ import annotations

from typing import Any

from cli.commands.workout import _fmt_hr_zone, _fmt_target, _range_status, _zone_status

MPH = 1.609344


def _item(**over: Any) -> dict[str, Any]:
    return {"exercise_key": "bike", "position": 0, **over}


class TestHrZoneFormatting:
    def test_a_zone(self) -> None:
        assert _fmt_hr_zone(160, 175) == "HR 160-175"

    def test_floor_only(self) -> None:
        assert _fmt_hr_zone(120, None) == "HR 120+"

    def test_ceiling_only(self) -> None:
        assert _fmt_hr_zone(None, 145) == "HR ≤145"

    def test_equal_bounds_are_a_single_number(self) -> None:
        assert _fmt_hr_zone(150, 150) == "HR 150"

    def test_no_zone(self) -> None:
        assert _fmt_hr_zone(None, None) == ""


class TestTargetLine:
    def test_the_bike_interval_prescription(self) -> None:
        """2 min on at HR 160-175, fallback 170/min or 20 mph."""
        out = _fmt_target(
            _item(
                target_duration_seconds=120,
                target_hr_min=160,
                target_hr_max=175,
                target_cadence=170,
                target_speed_kph=20 * MPH,
            )
        )
        assert "HR 160-175" in out
        assert "170/min" in out
        assert "20mph" in out

    def test_the_aerobic_day_ceiling(self) -> None:
        out = _fmt_target(_item(target_duration_seconds=1200, target_hr_min=120, target_hr_max=145))
        assert "HR 120-145" in out

    def test_items_without_hr_are_unchanged(self) -> None:
        assert _fmt_target(_item(exercise_key="pushups", target_reps=15)) == "15 reps"


class TestZoneStatus:
    def test_inside_the_zone(self) -> None:
        assert "in zone" in _zone_status(168, 160, 175)

    def test_bounds_are_inclusive(self) -> None:
        assert "in zone" in _zone_status(160, 160, 175)
        assert "in zone" in _zone_status(175, 160, 175)

    def test_below_the_zone_is_a_warning_not_a_failure(self) -> None:
        assert "below zone" in _zone_status(140, 160, 175)

    def test_above_the_zone_is_red(self) -> None:
        """The point of "keep HR 120-145" is not going harder — unlike reps,
        exceeding a heart-rate ceiling is the opposite of the prescription."""
        assert "above zone" in _zone_status(165, 120, 145)
        assert "red" in _zone_status(165, 120, 145)

    def test_hr_does_not_reuse_the_rep_grader(self) -> None:
        """Guard against a refactor collapsing the two: over a rep range is
        over-delivery (green), over an HR ceiling is not."""
        assert "green" in _range_status(14, 8, 12)  # reps: over is good
        assert "red" in _zone_status(165, 120, 145)  # HR: over is not

    def test_no_zone_grades_nothing(self) -> None:
        assert _zone_status(150, None, None) == ""
