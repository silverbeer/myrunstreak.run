"""Data mappers for converting between API models and Supabase schema."""

from typing import Any
from uuid import UUID

from ..models import Activity, Split


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
    return {
        # Multi-user identifiers
        "user_id": str(user_id),
        "source_id": str(source_id),
        "source_activity_id": activity.activity_id,  # Their API ID
        "external_id": activity.external_id,
        # Temporal data (computed fields handled by trigger)
        "start_date_time_local": activity.start_date_time_local.isoformat(),
        # Core metrics
        "distance_km": float(activity.distance),
        "duration_seconds": float(activity.duration),
        # Cadence (cast to int - database expects integer)
        "cadence_average": (int(activity.cadence_average) if activity.cadence_average else None),
        "cadence_min": int(activity.cadence_min) if activity.cadence_min else None,
        "cadence_max": int(activity.cadence_max) if activity.cadence_max else None,
        # Heart rate (cast to int - database expects integer)
        "heart_rate_average": int(activity.heart_rate_average) if activity.heart_rate_average else None,
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
        "weather_type": (activity.weather_type.value if activity.weather_type else None),
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


def split_to_dict(split: Split, run_id: UUID) -> dict[str, Any]:
    """
    Convert Split model to Supabase splits table format.

    Args:
        split: Split model
        run_id: Run UUID (foreign key)

    Returns:
        Dict ready for Supabase insert/upsert
    """
    return {
        "run_id": str(run_id),
        "split_number": split.split_number,
        "split_unit": split.split_unit,
        "cumulative_distance_km": float(split.cumulative_distance),
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
