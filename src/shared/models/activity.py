"""Run activity data models."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from .enums import ActivityType, DeviceType, HowFelt, Terrain, WeatherType
from .nested import HeartRateRecovery, Lap, Song


class Activity(BaseModel):
    """
    Represents a complete running activity from SmashRun API.

    This model captures both summary metrics and optional time series data.
    All distance values are in kilometers, all durations in seconds.
    """

    # Required Fields
    activity_id: str = Field(
        description="Unique identifier for the run",
        alias="activityId",
    )
    start_date_time_local: datetime = Field(
        description="Run start time in local timezone with offset",
        alias="startDateTimeLocal",
    )
    distance: float = Field(
        description="Total distance in kilometers",
        gt=0,
    )
    duration: int = Field(
        description="Total duration in seconds, excluding pauses",
        gt=0,
    )

    # Metadata
    activity_type: ActivityType = Field(
        default=ActivityType.RUNNING,
        description="Type of activity",
        alias="activityType",
    )
    external_id: str | None = Field(
        default=None,
        description="App-specific identifier for deduplication",
        alias="externalId",
    )
    external_app_version: str | None = Field(
        default=None,
        description="Version of recording software",
        alias="externalAppVersion",
    )
    external_device_type: DeviceType | None = Field(
        default=None,
        description="Device platform used for recording",
        alias="externalDeviceType",
    )

    # Performance Metrics - Cadence
    cadence_average: float | None = Field(
        default=None,
        description="Average cadence in steps per minute (weighted by duration)",
        alias="cadenceAverage",
        ge=0,
    )
    cadence_min: float | None = Field(
        default=None,
        description="Minimum cadence in steps per minute",
        alias="cadenceMin",
        ge=0,
    )
    cadence_max: float | None = Field(
        default=None,
        description="Maximum cadence in steps per minute",
        alias="cadenceMax",
        ge=0,
    )

    # Performance Metrics - Heart Rate
    heart_rate_average: float | None = Field(
        default=None,
        description="Average heart rate in beats per minute (weighted)",
        alias="heartRateAverage",
        ge=0,
    )
    heart_rate_min: float | None = Field(
        default=None,
        description="Minimum heart rate in beats per minute",
        alias="heartRateMin",
        ge=0,
    )
    heart_rate_max: float | None = Field(
        default=None,
        description="Maximum heart rate in beats per minute",
        alias="heartRateMax",
        ge=0,
    )

    # Environmental & Health Data
    body_weight: float | None = Field(
        default=None,
        description="Athlete weight in kilograms on run date",
        alias="bodyWeight",
        gt=0,
    )
    how_felt: HowFelt | None = Field(
        default=None,
        description="Subjective feeling during the run",
        alias="howFelt",
    )
    terrain: Terrain | None = Field(
        default=None,
        description="Type of running surface",
    )
    temperature: int | None = Field(
        default=None,
        description="Average temperature in Celsius",
        alias="temperature",
    )
    weather_type: WeatherType | None = Field(
        default=None,
        description="Weather conditions during the run",
        alias="weatherType",
    )
    humidity: int | None = Field(
        default=None,
        description="Humidity percentage (0-100)",
        ge=0,
        le=100,
    )
    wind_speed: int | None = Field(
        default=None,
        description="Average wind speed in kilometers per hour",
        alias="windSpeed",
        ge=0,
    )

    # User Content
    notes: str | None = Field(
        default=None,
        description="User description of the run",
        max_length=800,
    )

    # Time Series Data
    recording_keys: list[str] | None = Field(
        default=None,
        description="Names of data series in recordingValues",
        alias="recordingKeys",
    )
    recording_values: list[list[float]] | None = Field(
        default=None,
        description="Time series data arrays corresponding to recordingKeys",
        alias="recordingValues",
    )

    # Nested Objects
    laps: list[Lap] | None = Field(
        default=None,
        description="Lap segments within the run",
    )
    songs: list[Song] | None = Field(
        default=None,
        description="Songs played during the run",
    )
    heart_rate_recovery: list[HeartRateRecovery] | None = Field(
        default=None,
        description="Heart rate recovery measurements after run",
        alias="heartRateRecovery",
    )

    # Pause Information
    pause_indexes: list[int] | None = Field(
        default=None,
        description="0-based indexes in recordingValues following pauses",
        alias="pauseIndexes",
    )

    model_config = {"populate_by_name": True}

    @field_validator("recording_values")
    @classmethod
    def validate_recording_values(
        cls, v: list[list[float]] | None, info
    ) -> list[list[float]] | None:
        """Ensure recording_values length matches recording_keys if both are present."""
        if v is not None:
            recording_keys = info.data.get("recording_keys")
            if recording_keys is not None and len(v) != len(recording_keys):
                raise ValueError(
                    f"recording_values length ({len(v)}) must match "
                    f"recording_keys length ({len(recording_keys)})"
                )
        return v

    @property
    def average_pace_min_per_km(self) -> float:
        """Calculate average pace in minutes per kilometer."""
        if self.distance > 0 and self.duration > 0:
            return (self.duration / 60) / self.distance
        return 0.0

    @property
    def average_speed_kph(self) -> float:
        """Calculate average speed in kilometers per hour."""
        if self.duration > 0:
            return (self.distance / self.duration) * 3600
        return 0.0

    # Imperial unit properties (miles-based)
    @property
    def distance_miles(self) -> float:
        """Get distance in miles."""
        from .units import km_to_miles

        return km_to_miles(self.distance)

    @property
    def average_pace_min_per_mile(self) -> float:
        """Calculate average pace in minutes per mile."""
        if self.distance_miles > 0 and self.duration > 0:
            return (self.duration / 60) / self.distance_miles
        return 0.0

    @property
    def average_speed_mph(self) -> float:
        """Calculate average speed in miles per hour."""
        if self.duration > 0:
            return (self.distance_miles / self.duration) * 3600
        return 0.0
