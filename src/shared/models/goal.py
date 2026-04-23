"""Running goal data model."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class Goal(BaseModel):
    """
    Represents a yearly or monthly running goal from SmashRun API.

    Distance stored in kilometers (SmashRun's native unit) to stay consistent
    with runs.distance_km. Imperial conversions are exposed as properties.

    SmashRun API shape:
        {"goalText": "...", "goalKilometers": 2500.0, "kilometers": 847.3}
    """

    year: int = Field(description="Goal year", ge=2000, le=2100)
    month: int | None = Field(
        default=None,
        description="Goal month (1-12) or None for yearly goal",
        ge=1,
        le=12,
    )

    goal_text: str | None = Field(
        default=None,
        description="Human-readable goal description from SmashRun",
        alias="goalText",
    )
    goal_km: float | None = Field(
        default=None,
        description="Target distance in kilometers",
        alias="goalKilometers",
        gt=0,
    )
    progress_km: float | None = Field(
        default=None,
        description="Current progress toward goal in kilometers",
        alias="kilometers",
        ge=0,
    )

    fetched_at: datetime | None = Field(
        default=None,
        description="When this goal was fetched from the API",
    )

    model_config = {"populate_by_name": True}

    @field_validator("goal_km", "progress_km", mode="before")
    @classmethod
    def coerce_numeric(cls, v: float | int | str | None) -> float | None:
        """Coerce numeric-like values, treating 0 as None for goal_km only via validator."""
        if v is None or v == "":
            return None
        return float(v)

    @property
    def is_yearly(self) -> bool:
        """True if this is a yearly goal (no month)."""
        return self.month is None

    @property
    def goal_miles(self) -> float | None:
        """Goal distance in miles."""
        from .units import km_to_miles

        return km_to_miles(self.goal_km) if self.goal_km is not None else None

    @property
    def progress_miles(self) -> float | None:
        """Progress distance in miles."""
        from .units import km_to_miles

        return km_to_miles(self.progress_km) if self.progress_km is not None else None

    @property
    def progress_percent(self) -> float | None:
        """Percent of goal completed (0-100+). None if goal_km missing or zero."""
        if not self.goal_km or self.progress_km is None:
            return None
        return (self.progress_km / self.goal_km) * 100
