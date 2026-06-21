"""Athlete Training Tracker — workout models (SB-190).

Structured S&C workouts: a coach's template, logged sessions, and the per-
exercise sets actually performed. Mirrors the schema in
supabase/migrations/20260620000000_create_workouts.sql. Additive to the metric
engine; see the Athlete Training Tracker epic.

Loads are canonical kg, distances canonical m (convert at the presentation edge).
Each exercise records only the dimensions it uses (reps / duration_seconds /
load_kg / distance_m / time_seconds) — same wide-nullable approach as splits.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ExerciseCategory(StrEnum):
    strength = "strength"
    speed = "speed"
    power = "power"
    mobility = "mobility"
    cardio = "cardio"
    test = "test"  # benchmark tests: 40yd dash, vertical, broad jump, 5-10-5


class WorkoutType(StrEnum):
    circuit = "circuit"
    intervals = "intervals"
    test = "test"
    session = "session"


class Exercise(BaseModel):
    """A row in the global movement catalog."""

    key: str
    display_name: str
    category: ExerciseCategory
    measures: list[str] = Field(default_factory=list)
    is_benchmark: bool = False


# --------------------------------------------------------------------------- #
# Templates (the coach's prescribed plan)
# --------------------------------------------------------------------------- #
class TemplateItemCreate(BaseModel):
    """One prescribed exercise within a template."""

    exercise_key: str
    position: int = 0
    target_reps: int | None = Field(default=None, ge=0)
    target_duration_seconds: float | None = Field(default=None, ge=0)
    target_load_kg: float | None = Field(default=None, ge=0)
    target_distance_m: float | None = Field(default=None, ge=0)
    rest_seconds: float | None = Field(default=None, ge=0)
    variant: str | None = None
    notes: str | None = None


class TemplateItem(TemplateItemCreate):
    id: UUID
    user_id: UUID
    template_id: UUID


class WorkoutTemplateCreate(BaseModel):
    """Input for creating a template, optionally with its items inline."""

    name: str
    type: WorkoutType = WorkoutType.circuit
    rounds: int = Field(default=1, ge=1)
    source: str | None = None
    notes: str | None = None
    items: list[TemplateItemCreate] = Field(default_factory=list)


class WorkoutTemplate(BaseModel):
    """A stored template."""

    id: UUID
    user_id: UUID
    athlete_id: UUID | None = None
    created_by: UUID | None = None
    name: str
    type: WorkoutType
    rounds: int
    source: str | None = None
    notes: str | None = None
    items: list[TemplateItem] = Field(default_factory=list)
    created_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Sessions + sets (the actual performance)
# --------------------------------------------------------------------------- #
class ExerciseSetCreate(BaseModel):
    """One logged set. Fills only the dimensions the exercise uses."""

    exercise_key: str
    round_number: int | None = Field(default=None, ge=1)
    set_index: int | None = Field(default=None, ge=1)
    variant: str | None = None
    reps: int | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    load_kg: float | None = Field(default=None, ge=0)
    distance_m: float | None = Field(default=None, ge=0)
    time_seconds: float | None = Field(default=None, ge=0)
    rpe: int | None = Field(default=None, ge=1, le=10)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    notes: str | None = None
    extra: dict[str, Any] | None = None


class ExerciseSet(ExerciseSetCreate):
    id: UUID
    user_id: UUID
    session_id: UUID


class WorkoutSessionCreate(BaseModel):
    """Input for logging a session, optionally with its sets inline."""

    session_date: date
    template_id: UUID | None = None
    type: WorkoutType = WorkoutType.circuit
    total_minutes: float | None = Field(default=None, ge=0)
    how_felt: str | None = None
    notes: str | None = None
    sets: list[ExerciseSetCreate] = Field(default_factory=list)


class WorkoutSession(BaseModel):
    """A stored session with its sets."""

    id: UUID
    user_id: UUID
    athlete_id: UUID | None = None
    created_by: UUID | None = None
    session_date: date
    template_id: UUID | None = None
    type: WorkoutType
    total_minutes: float | None = None
    how_felt: str | None = None
    notes: str | None = None
    sets: list[ExerciseSet] = Field(default_factory=list)
    created_at: datetime | None = None
