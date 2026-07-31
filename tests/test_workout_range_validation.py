"""SB-446: a range target whose max sits below its min is rejected at the edge.

Matthew's prescriptions are ranges — "8-12x200", "5-8lb dumbbells", "60-90
second rest". A transposed pair would render as "12-8 reps" on Gabe's sheet, so
it is caught in the model rather than surfacing as a database CHECK violation.
"""

import pytest
from pydantic import ValidationError

from src.shared.models.workout import ExerciseSetCreate, RestMode, TemplateItemCreate


def test_ordered_ranges_are_accepted() -> None:
    item = TemplateItemCreate(
        exercise_key="interval_run",
        target_reps=8,
        target_reps_max=12,
        target_duration_seconds=40,
        target_duration_max_seconds=42,
        rest_seconds=60,
        rest_seconds_max=90,
        rest_mode=RestMode.autoregulated,
    )
    assert item.target_reps_max == 12
    assert item.rest_mode == "autoregulated"


def test_equal_bounds_are_fine() -> None:
    assert TemplateItemCreate(exercise_key="pushups", target_reps=10, target_reps_max=10)


@pytest.mark.parametrize(
    "kwargs,field",
    [
        ({"target_reps": 12, "target_reps_max": 8}, "target_reps_max"),
        ({"target_load_kg": 10.0, "target_load_max_kg": 5.0}, "target_load_max_kg"),
        ({"rest_seconds": 90, "rest_seconds_max": 60}, "rest_seconds_max"),
        (
            {"target_duration_seconds": 42, "target_duration_max_seconds": 40},
            "target_duration_max_seconds",
        ),
    ],
)
def test_inverted_range_is_rejected(kwargs: dict[str, float], field: str) -> None:
    with pytest.raises(ValidationError) as exc:
        TemplateItemCreate(exercise_key="pushups", **kwargs)
    assert field in str(exc.value)


def test_a_lone_bound_is_allowed() -> None:
    """Only a max ("≤22s") or only a min ("15+ reps") are both real prescriptions."""
    assert TemplateItemCreate(exercise_key="pushups", target_reps_max=12)
    assert TemplateItemCreate(exercise_key="pushups", target_reps=8)


def test_rest_mode_is_constrained() -> None:
    assert TemplateItemCreate(exercise_key="pushups", rest_mode=RestMode.full).rest_mode == "full"
    with pytest.raises(ValidationError):
        TemplateItemCreate(exercise_key="pushups", rest_mode="whenever")


def test_full_recovery_needs_no_number() -> None:
    """ "Full recovery" is a condition, not a duration."""
    item = TemplateItemCreate(exercise_key="ground_start_accel", rest_mode=RestMode.full)
    assert item.rest_seconds is None
    assert item.rest_mode == "full"


def test_existing_items_are_unaffected() -> None:
    item = TemplateItemCreate(exercise_key="pushups", target_reps=15)
    assert item.target_reps_max is None
    assert item.rest_mode is None


# --- HR / cadence / speed (SB-447) -------------------------------------------


def test_hr_zone_round_trips() -> None:
    item = TemplateItemCreate(
        exercise_key="bike",
        target_hr_min=160,
        target_hr_max=175,
        target_cadence=170,
        target_speed_kph=32.19,
    )
    assert (item.target_hr_min, item.target_hr_max) == (160, 175)
    assert item.target_cadence == 170


def test_inverted_hr_zone_is_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        TemplateItemCreate(exercise_key="bike", target_hr_min=175, target_hr_max=160)
    assert "target_hr_max" in str(exc.value)


@pytest.mark.parametrize("bpm", [10, 610])
def test_impossible_heart_rates_are_rejected(bpm: int) -> None:
    """Bounds catch a transposed digit, not implausible coaching."""
    with pytest.raises(ValidationError):
        TemplateItemCreate(exercise_key="bike", target_hr_min=bpm)


def test_matthews_170_cadence_is_allowed() -> None:
    """170 is not sustainable bike cadence and is probably running cadence in
    steps/min — but it is what the coach wrote, and rejecting it in the model
    would block his plan before he has been asked. The judgement stays advisory
    in the log-workout skill.
    """
    assert TemplateItemCreate(exercise_key="bike", target_cadence=170).target_cadence == 170


def test_logged_set_carries_hr_cadence_speed() -> None:
    st = ExerciseSetCreate(
        exercise_key="bike", hr_bpm_avg=168, hr_bpm_max=181, cadence=95, speed_kph=32.19
    )
    assert st.hr_bpm_avg == 168
    assert st.speed_kph == 32.19


def test_logged_hr_max_below_average_is_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        ExerciseSetCreate(exercise_key="bike", hr_bpm_avg=180, hr_bpm_max=150)
    assert "hr_bpm_max" in str(exc.value)


def test_sets_without_the_new_measures_are_unchanged() -> None:
    st = ExerciseSetCreate(exercise_key="pushups", reps=15)
    assert st.hr_bpm_avg is None
    assert st.cadence is None
