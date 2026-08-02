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

from pydantic import BaseModel, Field, model_validator


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


class RestMode(StrEnum):
    """How rest between efforts is prescribed (SB-446).

    Matthew writes rest three different ways, and two of them are not numbers:
    "60-90 second rest (go off how you feel)" is a range the athlete resolves,
    and "full recovery before ground-to-sprint accelerations" is a condition.
    """

    fixed = "fixed"  # rest_seconds exactly
    range = "range"  # rest_seconds..rest_seconds_max
    full = "full"  # full recovery — until ready, no number
    autoregulated = "autoregulated"  # "go off how you feel"


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
    # lower bound (SB-264). Reps, load and rest follow the same convention
    # (SB-446) — Matthew prescribes "8-12x200", "5-8lb", "60-90 second rest".
    target_duration_max_seconds: float | None = Field(default=None, ge=0)
    target_reps_max: int | None = Field(default=None, ge=0)
    target_load_kg: float | None = Field(default=None, ge=0)
    target_load_max_kg: float | None = Field(default=None, ge=0)
    target_distance_m: float | None = Field(default=None, ge=0)
    rest_seconds: float | None = Field(default=None, ge=0)
    rest_seconds_max: float | None = Field(default=None, ge=0)
    # Heart rate, cadence and speed (SB-447) — the 2026-07-30 plan is the first
    # to prescribe them ("HR 160-175", "170 rpm or 20 mph"). Speed is canonical
    # kph, shown as mph at the edge. Cadence is a per-minute count whose unit
    # follows the movement: crank rpm cycling, steps running, skips on a rope.
    target_hr_min: int | None = Field(default=None, ge=20, le=250)
    target_hr_max: int | None = Field(default=None, ge=20, le=250)
    target_cadence: float | None = Field(default=None, ge=0, le=300)
    target_speed_kph: float | None = Field(default=None, ge=0, le=100)
    # "Full recovery" and "go off how you feel" are prescriptions, not numbers —
    # storing them as a mode beats inventing a value the coach never gave.
    rest_mode: RestMode | None = None
    # Per-segment goals for a broken rep (SB-264); None for ordinary items.
    segments: list[SegmentTarget] | None = None
    variant: str | None = None
    # Alternatives (SB-448): items sharing an option_group are a "pick one of N"
    # — the aerobic day is run OR bike OR jump rope, not all three. None =
    # mandatory. The label is read from any member of the group.
    option_group: str | None = None
    option_group_label: str | None = None
    # Which circuit this item belongs to (SB-527). On CREATE the blocks do not
    # have ids yet, so the payload references them by index into `blocks` and
    # the repository resolves it to a real block_id. Deliberately transient —
    # persisting another string key is the pattern this table is escaping.
    block_index: int | None = Field(default=None, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def _ranges_are_ordered(self) -> TemplateItemCreate:
        """A max below its min would render as "12-8 reps" — reject at the edge.

        Mirrored by CHECK constraints in the migration; this catches it before a
        round-trip and gives a field-level error instead of a database one.
        """
        pairs = (
            ("target_reps", "target_reps_max"),
            ("target_load_kg", "target_load_max_kg"),
            ("rest_seconds", "rest_seconds_max"),
            ("target_hr_min", "target_hr_max"),
            ("target_duration_seconds", "target_duration_max_seconds"),
        )
        for lo_name, hi_name in pairs:
            lo, hi = getattr(self, lo_name), getattr(self, hi_name)
            if lo is not None and hi is not None and hi < lo:
                raise ValueError(f"{hi_name} ({hi}) is below {lo_name} ({lo})")
        return self


class TemplateItem(TemplateItemCreate):
    id: UUID
    user_id: UUID
    template_id: UUID
    # Resolved circuit membership (SB-527); None for items outside any circuit.
    block_id: UUID | None = None


class TemplateBlockCreate(BaseModel):
    """A circuit within a template (SB-527).

    Rounds belong here, not on the template. Gabe's Monday workout is "Circuit A
    twice, then four minutes water, then Circuit B once" — one number on the
    template could not say that, so the real prescription lived in prose and
    nothing could render or track it.
    """

    label: str
    position: int = 0
    rounds: int = Field(default=1, ge=1)
    rest_after_seconds: float | None = Field(default=None, ge=0)


class TemplateBlock(TemplateBlockCreate):
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
    scheduled_for: date | None = None  # optional date the workout is for (SB-335)
    # Circuits, in order. Items reference them by `block_index` (SB-527).
    blocks: list[TemplateBlockCreate] = Field(default_factory=list)
    items: list[TemplateItemCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _block_index_in_range(self) -> WorkoutTemplateCreate:
        """A dangling block_index would silently orphan the item."""
        for it in self.items:
            if it.block_index is not None and it.block_index >= len(self.blocks):
                raise ValueError(
                    f"block_index {it.block_index} has no matching block "
                    f"(there {'is' if len(self.blocks) == 1 else 'are'} {len(self.blocks)})"
                )
        return self


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
    scheduled_for: date | None = None  # optional date the workout is for (SB-335)
    blocks: list[TemplateBlock] = Field(default_factory=list)
    items: list[TemplateItem] = Field(default_factory=list)
    created_at: datetime | None = None
    # Completion (SB-334), populated by the list query: a template is "done"
    # when a logged session references it. False/None on single-template reads.
    has_session: bool = False
    last_session_date: date | None = None
    # How many sessions reference this template (SB-530) — the "done 5x" the
    # Plans tab shows, which turns a library into something with history rather
    # than a filing cabinet. Same batched query as has_session, so it costs
    # nothing extra. 0 on single-template reads, where that join is not run.
    session_count: int = 0


# --------------------------------------------------------------------------- #
# Schedule (a plan put on a day, by someone)
# --------------------------------------------------------------------------- #
class WorkoutScheduleCreate(BaseModel):
    """Input for putting a template on a date (SB-534)."""

    template_id: UUID
    scheduled_for: date
    notes: str | None = None


class WorkoutSchedule(BaseModel):
    """One planned occasion.

    `created_by` is the point of the row: either a coach or the athlete may
    schedule, and the screen has to say which without being told.
    """

    id: UUID
    user_id: UUID
    athlete_id: UUID | None = None
    created_by: UUID | None = None
    template_id: UUID
    scheduled_for: date
    notes: str | None = None
    created_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Sessions + sets (the actual performance)
# --------------------------------------------------------------------------- #
class ExerciseSetCreate(BaseModel):
    """One logged set. Fills only the dimensions the exercise uses."""

    exercise_key: str
    # Which prescribed item this set answers (SB-527). None for ad-hoc sets with
    # no prescription behind them. Without it "lunge, round 1, 45s" cannot be
    # attributed — `lunge` appears five times in one of Matthew's templates.
    template_item_id: UUID | None = None
    round_number: int | None = Field(default=None, ge=1)
    set_index: int | None = Field(default=None, ge=1)
    variant: str | None = None
    reps: int | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    load_kg: float | None = Field(default=None, ge=0)
    distance_m: float | None = Field(default=None, ge=0)
    time_seconds: float | None = Field(default=None, ge=0)
    # Measured HR / cadence / speed (SB-447). Bounds catch a transposed 610 bpm,
    # not implausible coaching — judging whether a value is realistic stays with
    # the log-workout skill, which flags outliers to a human.
    hr_bpm_avg: int | None = Field(default=None, ge=20, le=250)
    hr_bpm_max: int | None = Field(default=None, ge=20, le=250)
    cadence: float | None = Field(default=None, ge=0, le=300)
    speed_kph: float | None = Field(default=None, ge=0, le=100)
    rpe: int | None = Field(default=None, ge=1, le=10)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    notes: str | None = None
    extra: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _hr_max_not_below_avg(self) -> ExerciseSetCreate:
        if self.hr_bpm_avg is not None and self.hr_bpm_max is not None:
            if self.hr_bpm_max < self.hr_bpm_avg:
                raise ValueError(
                    f"hr_bpm_max ({self.hr_bpm_max}) is below hr_bpm_avg ({self.hr_bpm_avg})"
                )
        return self


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
    # What was logged, populated by the list query (SB-530), which returns no
    # sets: a session row has to be able to say "22 exercises logged" without
    # the caller fetching each session in turn. Both are 0 on a single-session
    # read, where `sets` is present and carries the same answer.
    set_count: int = 0
    exercise_count: int = 0
