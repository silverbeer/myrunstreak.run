"""Round-trip tests for workout models (SB-190).

Proves the model handles both shapes the trainer uses: a multi-round circuit and
a 40-yd-dash performance test.
"""

from __future__ import annotations

from datetime import date

from src.shared.models import (
    ExerciseSetCreate,
    TemplateItemCreate,
    WorkoutSessionCreate,
    WorkoutTemplateCreate,
    WorkoutType,
)

YARD_M = 0.9144
FORTY_YD_M = 40 * YARD_M


def test_circuit_template_round_trips():
    # Matthew's Saturday circuit (subset), 3 rounds.
    t = WorkoutTemplateCreate(
        name="Saturday Circuit",
        type=WorkoutType.circuit,
        rounds=3,
        source="Matthew",
        items=[
            TemplateItemCreate(exercise_key="jump_rope", position=0, target_duration_seconds=180),
            TemplateItemCreate(exercise_key="pushups", position=1, target_duration_seconds=30),
            TemplateItemCreate(
                exercise_key="bicep_hold",
                position=2,
                target_duration_seconds=60,
                target_load_kg=9.07,
            ),
            TemplateItemCreate(
                exercise_key="plank", position=3, target_duration_seconds=60, variant="front"
            ),
        ],
    )
    assert t.rounds == 3
    assert len(t.items) == 4
    assert t.items[2].target_load_kg == 9.07


def test_circuit_session_with_sets_and_rest_timeline():
    # A logged round of the circuit, with per-set wall-clock for rest/density.
    s = WorkoutSessionCreate(
        session_date=date(2026, 6, 20),
        type=WorkoutType.circuit,
        total_minutes=32.0,
        how_felt="strong",
        sets=[
            ExerciseSetCreate(exercise_key="jump_rope", round_number=1, duration_seconds=180),
            ExerciseSetCreate(exercise_key="pushups", round_number=1, reps=22, rpe=8),
            ExerciseSetCreate(exercise_key="lunge", round_number=1, reps=10, variant="left"),
            ExerciseSetCreate(exercise_key="lunge", round_number=1, reps=10, variant="right"),
        ],
    )
    assert len(s.sets) == 4
    assert s.sets[1].reps == 22
    assert {st.variant for st in s.sets if st.exercise_key == "lunge"} == {"left", "right"}


def test_40yd_dash_test_result():
    # A performance test: fixed distance, measured time — the speed progress marker.
    s = WorkoutSessionCreate(
        session_date=date(2026, 6, 20),
        type=WorkoutType.test,
        sets=[
            ExerciseSetCreate(
                exercise_key="40yd_dash", distance_m=FORTY_YD_M, time_seconds=5.42, set_index=1
            ),
        ],
    )
    dash = s.sets[0]
    assert dash.exercise_key == "40yd_dash"
    assert dash.time_seconds == 5.42
    assert round(dash.distance_m, 2) == round(FORTY_YD_M, 2)
