"""SB-446: a range target whose max sits below its min is rejected at the edge.

Matthew's prescriptions are ranges — "8-12x200", "5-8lb dumbbells", "60-90
second rest". A transposed pair would render as "12-8 reps" on Gabe's sheet, so
it is caught in the model rather than surfacing as a database CHECK violation.
"""

import pytest
from pydantic import ValidationError

from src.shared.models.workout import RestMode, TemplateItemCreate


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
