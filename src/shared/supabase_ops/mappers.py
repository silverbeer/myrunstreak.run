"""Data mappers for converting between API models and Supabase schema."""

from typing import Any
from uuid import UUID

from ..models import Activity, Split

# Map SmashRun weather types to database enum values
# Database: 'sunny', 'cloudy', 'rainy', 'snowy', 'windy', 'hot', 'cold'
WEATHER_TYPE_MAP: dict[str, str | None] = {
    "clear": "sunny",
    "cloudy": "cloudy",
    "partlycloudy": "cloudy",
    "rain": "rainy",
    "drizzle": "rainy",
    "extremerain": "rainy",
    "storm": "rainy",
    "snow": "snowy",
    "blizzard": "snowy",
    "extremecold": "cold",
    "extremewind": "windy",
    "indoor": None,  # No outdoor weather for indoor runs
}


def map_weather_type(smashrun_weather: str | None) -> str | None:
    """Map SmashRun weather type to database enum value."""
    if not smashrun_weather:
        return None
    return WEATHER_TYPE_MAP.get(smashrun_weather, None)


def activity_to_run_dict(activity: Activity, user_id: UUID, source_id: UUID) -> dict[str, Any]:
    """
    Convert Activity model to Supabase runs table format.

    Maps field names and adds multi-user/multi-source identifiers.

    Args:
        activity: Activity model from API response
        user_id: User UUID
        source_id: Source UUID (user_sources.id)

    Returns:
        Dict ready for Supabase insert/upsert
    """
    # Extract date from local time BEFORE any timezone conversion
    # This ensures the date matches the user's local date, not UTC
    local_dt = activity.start_date_time_local
    start_date = local_dt.date().isoformat()

    return {
        # Multi-user identifiers
        "user_id": str(user_id),
        "source_id": str(source_id),
        "source_activity_id": activity.activity_id,  # Their API ID
        "external_id": activity.external_id,
        # Temporal data - explicitly set date from local time
        "start_date_time_local": local_dt.isoformat(),
        "start_date": start_date,
        "start_year": local_dt.year,
        "start_month": local_dt.month,
        "start_day_of_week": local_dt.weekday(),
        "start_hour": local_dt.hour,
        # Core metrics
        "distance_km": float(activity.distance),
        "duration_seconds": float(activity.duration),
        # Cadence (cast to int - database expects integer)
        "cadence_average": (int(activity.cadence_average) if activity.cadence_average else None),
        "cadence_min": int(activity.cadence_min) if activity.cadence_min else None,
        "cadence_max": int(activity.cadence_max) if activity.cadence_max else None,
        # Heart rate (cast to int - database expects integer)
        "heart_rate_average": int(activity.heart_rate_average)
        if activity.heart_rate_average
        else None,
        "heart_rate_min": int(activity.heart_rate_min) if activity.heart_rate_min else None,
        "heart_rate_max": int(activity.heart_rate_max) if activity.heart_rate_max else None,
        # Health & subjective (filter "none" string values to NULL for enums)
        "body_weight_kg": (float(activity.body_weight) if activity.body_weight else None),
        "how_felt": (
            activity.how_felt.value
            if activity.how_felt and activity.how_felt.value != "none"
            else None
        ),
        # Environmental
        "terrain": (
            activity.terrain.value
            if activity.terrain and activity.terrain.value != "none"
            else None
        ),
        "temperature_celsius": (float(activity.temperature) if activity.temperature else None),
        "weather_type": map_weather_type(
            activity.weather_type.value if activity.weather_type else None
        ),
        "humidity_percent": int(activity.humidity) if activity.humidity else None,
        "wind_speed_kph": activity.wind_speed,
        # User content
        "notes": activity.notes,
        # Metadata
        "activity_type": activity.activity_type.value,
        "device_type": (
            activity.external_device_type.value if activity.external_device_type else None
        ),
        "app_version": activity.external_app_version,
        # Data availability flags
        "has_gps_data": (
            activity.recording_keys is not None and "latitude" in (activity.recording_keys or [])
        ),
        "has_heart_rate_data": activity.heart_rate_average is not None,
        "has_cadence_data": activity.cadence_average is not None,
        "has_splits": False,  # Will be updated when splits are added
        "has_laps": activity.laps is not None and len(activity.laps) > 0,
    }


MILES_TO_KM = 1.609344


def split_to_dict(
    split: Split,
    run_id: UUID,
    split_number: int | None = None,
    unit: str | None = None,
) -> dict[str, Any]:
    """
    Convert Split model to Supabase splits table format.

    ``split_number`` and ``unit`` are assigned at store time (SmashRun's splits
    payload carries neither). When ``unit == "mi"`` the split's
    ``cumulative_distance`` comes back in **miles**, so it's converted to km for
    the canonical ``cumulative_distance_km`` column; ``split_unit`` still records
    that these are **mile-boundary** splits (what "1st mile / 2nd mile" needs).

    Args:
        split: Split model
        run_id: Run UUID (foreign key)
        split_number: 1-based sequence; falls back to the model's value
        unit: "mi" or "km"; falls back to the model's value

    Returns:
        Dict ready for Supabase insert/upsert
    """
    resolved_unit = unit if unit is not None else split.split_unit
    distance = float(split.cumulative_distance)
    if resolved_unit == "mi":
        distance *= MILES_TO_KM
    return {
        "run_id": str(run_id),
        "split_number": split_number if split_number is not None else split.split_number,
        "split_unit": resolved_unit,
        "cumulative_distance_km": distance,
        "cumulative_seconds": float(split.cumulative_seconds),
        "speed_kph": float(split.speed_kph) if split.speed_kph else None,
        "heart_rate": split.heart_rate,
        "cumulative_elevation_gain_meters": (
            float(split.cumulative_elevation_gain_meters)
            if split.cumulative_elevation_gain_meters
            else None
        ),
        "cumulative_elevation_loss_meters": (
            float(split.cumulative_elevation_loss_meters)
            if split.cumulative_elevation_loss_meters
            else None
        ),
    }
