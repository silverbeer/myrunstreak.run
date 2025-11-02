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
    NONE = "none"  # When runner doesn't specify


class Terrain(str, Enum):
    """Type of running surface."""

    ROAD = "road"
    TRAIL = "trail"
    TRACK = "track"
    TREADMILL = "treadmill"
    BEACH = "beach"
    SNOWPACK = "snowpack"
    NONE = "none"  # When runner doesn't specify


class WeatherType(str, Enum):
    """Weather conditions during the run."""

    INDOOR = "indoor"
    CLEAR = "clear"
    CLOUDY = "cloudy"
    PARTLY_CLOUDY = "partlycloudy"
    RAIN = "rain"
    DRIZZLE = "drizzle"
    EXTREME_RAIN = "extremerain"
    STORM = "storm"
    SNOW = "snow"
    BLIZZARD = "blizzard"
    EXTREME_COLD = "extremecold"
    EXTREME_WIND = "extremewind"


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
