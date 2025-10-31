"""Unit conversion utilities for distance and speed."""

from enum import Enum


class UnitSystem(str, Enum):
    """Unit system for distance measurements."""

    METRIC = "metric"  # kilometers
    IMPERIAL = "imperial"  # miles


# Conversion constants
KM_TO_MILES = 0.621371
MILES_TO_KM = 1.609344


def km_to_miles(km: float) -> float:
    """
    Convert kilometers to miles.

    Args:
        km: Distance in kilometers

    Returns:
        Distance in miles
    """
    return km * KM_TO_MILES


def miles_to_km(miles: float) -> float:
    """
    Convert miles to kilometers.

    Args:
        miles: Distance in miles

    Returns:
        Distance in kilometers
    """
    return miles * MILES_TO_KM


def format_pace(pace_min_per_unit: float, unit: UnitSystem = UnitSystem.IMPERIAL) -> str:
    """
    Format pace as MM:SS per unit.

    Args:
        pace_min_per_unit: Pace in minutes per kilometer or mile
        unit: Unit system (for label only)

    Returns:
        Formatted pace string (e.g., "7:32 /mi" or "4:41 /km")
    """
    minutes = int(pace_min_per_unit)
    seconds = int((pace_min_per_unit - minutes) * 60)
    unit_label = "mi" if unit == UnitSystem.IMPERIAL else "km"
    return f"{minutes}:{seconds:02d} /{unit_label}"


def format_distance(distance: float, unit: UnitSystem = UnitSystem.IMPERIAL) -> str:
    """
    Format distance with appropriate unit label.

    Args:
        distance: Distance in kilometers or miles
        unit: Unit system for label

    Returns:
        Formatted distance string (e.g., "5.24 mi" or "8.43 km")
    """
    unit_label = "mi" if unit == UnitSystem.IMPERIAL else "km"
    return f"{distance:.2f} {unit_label}"
