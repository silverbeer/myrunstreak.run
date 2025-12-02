"""Tests for unit conversion utilities."""

from datetime import UTC, date, datetime

import pytest

from src.lambdas.publish_status.handler import format_streak_duration
from src.shared.models import (
    Activity,
    UnitSystem,
    format_distance,
    format_pace,
    km_to_miles,
    miles_to_km,
)


def test_km_to_miles_conversion():
    """Test kilometer to miles conversion."""
    assert km_to_miles(5.0) == pytest.approx(3.10686, rel=0.01)
    assert km_to_miles(10.0) == pytest.approx(6.21371, rel=0.01)
    assert km_to_miles(21.0975) == pytest.approx(13.1, rel=0.01)  # Half marathon
    assert km_to_miles(42.195) == pytest.approx(26.2, rel=0.01)  # Marathon


def test_miles_to_km_conversion():
    """Test miles to kilometers conversion."""
    assert miles_to_km(3.1) == pytest.approx(4.989, rel=0.01)
    assert miles_to_km(6.2) == pytest.approx(9.978, rel=0.01)
    assert miles_to_km(13.1) == pytest.approx(21.08, rel=0.01)  # Half marathon
    assert miles_to_km(26.2) == pytest.approx(42.165, rel=0.01)  # Marathon


def test_round_trip_conversion():
    """Test that converting back and forth maintains precision."""
    original_km = 10.0
    miles = km_to_miles(original_km)
    back_to_km = miles_to_km(miles)
    assert back_to_km == pytest.approx(original_km, rel=0.0001)


def test_format_distance_imperial():
    """Test distance formatting in miles."""
    assert format_distance(5.24, UnitSystem.IMPERIAL) == "5.24 mi"
    assert format_distance(13.1, UnitSystem.IMPERIAL) == "13.10 mi"


def test_format_distance_metric():
    """Test distance formatting in kilometers."""
    assert format_distance(8.43, UnitSystem.METRIC) == "8.43 km"
    assert format_distance(21.1, UnitSystem.METRIC) == "21.10 km"


def test_format_pace_imperial():
    """Test pace formatting in min/mile."""
    # 7:30 min/mile
    assert format_pace(7.5, UnitSystem.IMPERIAL) == "7:30 /mi"
    # 8:00 min/mile
    assert format_pace(8.0, UnitSystem.IMPERIAL) == "8:00 /mi"
    # 6:45 min/mile
    assert format_pace(6.75, UnitSystem.IMPERIAL) == "6:45 /mi"


def test_format_pace_metric():
    """Test pace formatting in min/km."""
    # 5:00 min/km
    assert format_pace(5.0, UnitSystem.METRIC) == "5:00 /km"
    # 4:30 min/km
    assert format_pace(4.5, UnitSystem.METRIC) == "4:30 /km"


def test_activity_imperial_properties():
    """Test that Activity model provides imperial unit properties."""
    # Create a 5K run in 30 minutes (stored in km)
    activity = Activity(
        activityId="test-imperial",
        startDateTimeLocal=datetime.now(UTC),
        distance=5.0,  # 5 km
        duration=1800,  # 30 minutes
    )

    # Distance should convert to miles
    assert activity.distance == 5.0  # Original km value
    assert activity.distance_miles == pytest.approx(3.10686, rel=0.01)

    # Pace should be available in both units
    # 5 km in 30 min = 6:00 min/km
    assert activity.average_pace_min_per_km == pytest.approx(6.0, rel=0.01)
    # 3.1 miles in 30 min = 9:40 min/mile
    assert activity.average_pace_min_per_mile == pytest.approx(9.656, rel=0.01)

    # Speed should be available in both units
    # 10 kph
    assert activity.average_speed_kph == pytest.approx(10.0, rel=0.01)
    # 6.21 mph
    assert activity.average_speed_mph == pytest.approx(6.21, rel=0.01)


def test_activity_imperial_realistic_example():
    """Test with realistic running data in miles."""
    # User thinks: "I ran 6.2 miles in 52 minutes"
    # We need to store as km, but they'll see miles

    distance_miles = 6.2
    distance_km = miles_to_km(distance_miles)
    duration_seconds = 52 * 60

    activity = Activity(
        activityId="test-10k",
        startDateTimeLocal=datetime.now(UTC),
        distance=distance_km,  # Store as km
        duration=duration_seconds,
    )

    # When they query, they get miles back
    assert activity.distance_miles == pytest.approx(6.2, rel=0.01)

    # Pace: 52 min / 6.2 miles = 8:23 min/mile
    expected_pace = 52.0 / 6.2
    assert activity.average_pace_min_per_mile == pytest.approx(expected_pace, rel=0.01)

    # Speed: 6.2 miles in 52 min = 7.15 mph
    expected_speed = 6.2 / (52 / 60)
    assert activity.average_speed_mph == pytest.approx(expected_speed, rel=0.01)


def test_zero_distance_handling():
    """Test that zero distance doesn't cause division errors."""
    activity = Activity(
        activityId="test-zero",
        startDateTimeLocal=datetime.now(UTC),
        distance=0.001,  # Minimal valid distance
        duration=1,
    )

    # Should not raise exceptions
    assert activity.distance_miles >= 0
    assert activity.average_pace_min_per_mile >= 0
    assert activity.average_speed_mph >= 0


# Tests for format_streak_duration
def test_format_streak_duration_years_months_days():
    """Test full format with years, months, and days."""
    today = date(2025, 3, 5)
    streak_start = "2013-11-30"  # 11 years, 3 months, 5 days
    result = format_streak_duration(streak_start, today)
    assert result == "11 years, 3 months and 5 days"


def test_format_streak_duration_singular():
    """Test singular form for 1 year, 1 month, 1 day."""
    today = date(2025, 2, 2)
    streak_start = "2024-01-01"  # 1 year, 1 month, 1 day
    result = format_streak_duration(streak_start, today)
    assert result == "1 year, 1 month and 1 day"


def test_format_streak_duration_days_only():
    """Test format with only days."""
    today = date(2025, 1, 15)
    streak_start = "2025-01-10"  # 5 days
    result = format_streak_duration(streak_start, today)
    assert result == "5 days"


def test_format_streak_duration_months_and_days():
    """Test format with months and days only."""
    today = date(2025, 3, 15)
    streak_start = "2025-01-10"  # 2 months and 5 days
    result = format_streak_duration(streak_start, today)
    assert result == "2 months and 5 days"


def test_format_streak_duration_years_and_days():
    """Test format with years and days only (no months)."""
    today = date(2025, 1, 15)
    streak_start = "2023-01-10"  # 2 years and 5 days
    result = format_streak_duration(streak_start, today)
    assert result == "2 years and 5 days"


def test_format_streak_duration_none_input():
    """Test that None input returns None."""
    result = format_streak_duration(None, date.today())
    assert result is None


def test_format_streak_duration_zero_days():
    """Test format when started today (0 days)."""
    today = date(2025, 1, 15)
    streak_start = "2025-01-15"  # Same day
    result = format_streak_duration(streak_start, today)
    assert result == "0 days"


def test_format_streak_duration_month_boundary():
    """Test across month boundaries with different day counts."""
    # March 2 with start Jan 31 - should handle different month lengths
    today = date(2025, 3, 2)
    streak_start = "2025-01-31"
    result = format_streak_duration(streak_start, today)
    assert result == "1 month and 2 days"
