"""Nested data models for run activities."""

from pydantic import BaseModel, Field

from .enums import LapType


class Lap(BaseModel):
    """Represents a lap segment within a run."""

    lap_type: LapType = Field(
        description="Type of lap segment",
        alias="lapType",
    )
    end_time: float | None = Field(
        default=None,
        description="End time in seconds for duration-based lap",
        alias="endTime",
    )
    end_distance: float | None = Field(
        default=None,
        description="End distance in meters for distance-based lap",
        alias="endDistance",
    )

    model_config = {"populate_by_name": True}


class Song(BaseModel):
    """Represents a song played during the run."""

    album: str | None = Field(default=None, description="Album name")
    artist: str | None = Field(default=None, description="Artist name")
    song: str = Field(description="Song title")
    bpm: int | None = Field(
        default=None,
        description="Beats per minute of the song",
        alias="BPM",
    )
    start_clock: float = Field(
        description="Start time in seconds from run start",
        alias="startClock",
    )
    end_clock: float = Field(
        description="End time in seconds from run start",
        alias="endClock",
    )

    model_config = {"populate_by_name": True}


class HeartRateRecovery(BaseModel):
    """Represents heart rate recovery measurement after run completion."""

    duration: int = Field(
        description="Time in seconds after run completion when measurement was taken"
    )
    heart_rate: float = Field(
        description="Heart rate in beats per minute",
        alias="heartRate",
    )

    model_config = {"populate_by_name": True}
