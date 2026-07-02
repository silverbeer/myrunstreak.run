"""Data models for MyRunStreak.com."""

from .activity import Activity
from .athlete import (
    ATHLETE_EDITABLE_FIELDS,
    Athlete,
    AthleteCreate,
    AthleteProfile,
    AthleteProfileUpdate,
    CoachAthlete,
    CoachAthleteStatus,
    Role,
)
from .enums import (
    ActivityType,
    DeviceType,
    HowFelt,
    LapType,
    Terrain,
    WeatherType,
)
from .goal import Goal
from .invite import Invite, InviteCreate
from .metric import (
    GoalComparator,
    GoalKind,
    GoalPeriod,
    GoalProgress,
    GoalStatus,
    MetricAggregation,
    MetricEntry,
    MetricEntryCreate,
    MetricGoal,
    MetricGoalCreate,
    MetricGoalUpdate,
    MetricType,
)
from .nested import HeartRateRecovery, Lap, Song
from .planning import (
    ActualEntry,
    FeasibilityStatus,
    GoalPlanStatus,
    PlanConstraint,
    PlanConstraintRecord,
    PlanDay,
    PlanDayKind,
    PlanningGoal,
    PlanResult,
    Readiness,
    ReadinessStatus,
)
from .split import Split
from .units import (
    UnitSystem,
    format_distance,
    format_pace,
    km_to_miles,
    miles_to_km,
)
from .workout import (
    Exercise,
    ExerciseCategory,
    ExerciseSet,
    ExerciseSetCreate,
    TemplateItem,
    TemplateItemCreate,
    WorkoutSession,
    WorkoutSessionCreate,
    WorkoutTemplate,
    WorkoutTemplateCreate,
    WorkoutType,
)

__all__ = [
    # Main models
    "Activity",
    "Goal",
    "Split",
    # Coach platform (SB-195)
    "ATHLETE_EDITABLE_FIELDS",
    "Athlete",
    "AthleteCreate",
    "AthleteProfile",
    "AthleteProfileUpdate",
    "CoachAthlete",
    "CoachAthleteStatus",
    "Role",
    # Invites
    "Invite",
    "InviteCreate",
    # Metric tracking
    "MetricType",
    "MetricEntry",
    "MetricEntryCreate",
    "MetricGoal",
    "MetricGoalCreate",
    "MetricGoalUpdate",
    "GoalProgress",
    "MetricAggregation",
    "GoalKind",
    "GoalPeriod",
    "GoalComparator",
    "GoalStatus",
    # Workouts
    "Exercise",
    "ExerciseCategory",
    "WorkoutType",
    "TemplateItem",
    "TemplateItemCreate",
    "WorkoutTemplate",
    "WorkoutTemplateCreate",
    "ExerciseSet",
    "ExerciseSetCreate",
    "WorkoutSession",
    "WorkoutSessionCreate",
    # Planning
    "ActualEntry",
    "PlanConstraint",
    "PlanConstraintRecord",
    "PlanDay",
    "PlanDayKind",
    "PlanningGoal",
    "PlanResult",
    "Readiness",
    "ReadinessStatus",
    "GoalPlanStatus",
    "FeasibilityStatus",
    # Nested models
    "Lap",
    "Song",
    "HeartRateRecovery",
    # Enums
    "ActivityType",
    "DeviceType",
    "HowFelt",
    "LapType",
    "Terrain",
    "WeatherType",
    # Units
    "UnitSystem",
    "km_to_miles",
    "miles_to_km",
    "format_distance",
    "format_pace",
]
