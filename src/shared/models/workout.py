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


class ExerciseVisibility(StrEnum):
    private = "private"  # owner only
    public = "public"  # canonical shared library


class MovementPattern(StrEnum):
    squat = "squat"
    hinge = "hinge"
    lunge = "lunge"
    push = "push"
    pull = "pull"
    carry = "carry"
    rotation = "rotation"
    anti_rotation = "anti_rotation"
    jump = "jump"
    sprint = "sprint"
    isometric = "isometric"
    mobility = "mobility"
    other = "other"


class Laterality(StrEnum):
    bilateral = "bilateral"
    unilateral = "unilateral"


class Difficulty(StrEnum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class ExerciseMeta(BaseModel):
    """Classification + presentation metadata shared by Exercise / create / update.

    All optional — the search/select component uses whatever is present (facets,
    balance nudge off movement_pattern, cues + media on the card and the
    printable take-home).
    """

    aliases: list[str] = Field(default_factory=list)  # synonyms → search + dedup
    movement_pattern: MovementPattern | None = None
    equipment: list[str] = Field(default_factory=list)
    body_region: list[str] = Field(default_factory=list)
    laterality: Laterality | None = None
    difficulty: Difficulty | None = None
    tags: list[str] = Field(default_factory=list)
    media_url: str | None = None
    thumbnail_url: str | None = None
    cues: list[str] = Field(default_factory=list)
    instructions: str | None = None


class Exercise(ExerciseMeta):
    """A row in the movement catalog — canonical (public) or coach-owned."""

    key: str
    display_name: str
    category: ExerciseCategory
    measures: list[str] = Field(default_factory=list)
    is_benchmark: bool = False
    owner_id: UUID | None = None  # NULL = canonical library
    visibility: ExerciseVisibility = ExerciseVisibility.public
    created_by: UUID | None = None
    forked_from: str | None = None


class ExerciseCreate(ExerciseMeta):
    """Coach adds an exercise. Private by default; publishable later. The key
    (slug) is generated server-side to stay globally unique."""

    display_name: str
    category: ExerciseCategory
    measures: list[str] = Field(default_factory=list)
    is_benchmark: bool = False
    visibility: ExerciseVisibility = ExerciseVisibility.private
    forked_from: str | None = None


class ExerciseUpdate(BaseModel):
    """Partial patch of an owned exercise (server enforces ownership)."""

    display_name: str | None = None
    category: ExerciseCategory | None = None
    measures: list[str] | None = None
    is_benchmark: bool | None = None
    visibility: ExerciseVisibility | None = None
    aliases: list[str] | None = None
    movement_pattern: MovementPattern | None = None
    equipment: list[str] | None = None
    body_region: list[str] | None = None
    laterality: Laterality | None = None
    difficulty: Difficulty | None = None
    tags: list[str] | None = None
    media_url: str | None = None
    thumbnail_url: str | None = None
    cues: list[str] | None = None
    instructions: str | None = None


# --------------------------------------------------------------------------- #
# Templates (the coach's prescribed plan)
# --------------------------------------------------------------------------- #
class SegmentTarget(BaseModel):
    """Goal for one segment of a broken rep (SB-264).

    E.g. a 400m broken into 100m sections: ``{distance_m: 100, target_s_min: 20,
    target_s_max: 22}``. A fixed goal sets only ``target_s_min``.
    """

    distance_m: float = Field(gt=0)
    target_s_min: float | None = Field(default=None, ge=0)
    target_s_max: float | None = Field(default=None, ge=0)
    label: str | None = None  # e.g. "0-100"


class TemplateItemCreate(BaseModel):
    """One prescribed exercise within a template."""

    exercise_key: str
    section: str = "main"  # warmup | main | cooldown (builder-defined grouping)
    position: int = 0
    target_reps: int | None = Field(default=None, ge=0)
    target_duration_seconds: float | None = Field(default=None, ge=0)
    # Upper bound when the goal is a range ("20-22 sec"); the field above is the
    # lower bound (SB-264).
    target_duration_max_seconds: float | None = Field(default=None, ge=0)
    target_load_kg: float | None = Field(default=None, ge=0)
    target_distance_m: float | None = Field(default=None, ge=0)
    rest_seconds: float | None = Field(default=None, ge=0)
    # Per-segment goals for a broken rep (SB-264); None for ordinary items.
    segments: list[SegmentTarget] | None = None
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
