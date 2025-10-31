"""Enumeration types for run data models."""

from enum import Enum


class ActivityType(str, Enum):
    """Type of physical activity."""

    RUNNING = "running"


class HowFelt(str, Enum):
    """Subjective feeling during the run."""

    UNSTOPPABLE = "Unstoppable"
    GREAT = "great"
    SO_SO = "soso"
    TIRED = "tired"
    INJURED = "injured"


class Terrain(str, Enum):
    """Type of running surface."""

    ROAD = "road"
    TRAIL = "trail"
    TRACK = "track"
    TREADMILL = "treadmill"
    BEACH = "beach"
    SNOWPACK = "snowpack"


class WeatherType(str, Enum):
    """Weather conditions during the run."""

    INDOOR = "indoor"
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    STORM = "storm"
    SNOW = "snow"


class DeviceType(str, Enum):
    """Device platform used for recording."""

    GOOGLE = "Google"
    APPLE = "Apple"
    RIM = "RIM"
    MICROSOFT = "Microsoft"
    SYMBIAN = "Symbian"
    OTHER = "Other"


class LapType(str, Enum):
    """Type of lap segment."""

    GENERAL = "general"
    WORK = "work"
    RECOVERY = "recovery"
    WARMUP = "warmup"
    COOLDOWN = "cooldown"
