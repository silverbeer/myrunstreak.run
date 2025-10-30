"""Tests for Pydantic data models."""

from datetime import datetime, timezone

import pytest

from src.shared.models import (
    Activity,
    ActivityType,
    HeartRateRecovery,
    HowFelt,
    Lap,
    LapType,
    Song,
    Terrain,
    WeatherType,
)


def test_minimal_activity():
    """Test creating an activity with only required fields."""
    activity = Activity(
        activityId="test-123",
        startDateTimeLocal=datetime.now(timezone.utc),
        distance=5.0,
        duration=1800,
    )

    assert activity.activity_id == "test-123"
    assert activity.distance == 5.0
    assert activity.duration == 1800
    assert activity.activity_type == ActivityType.RUNNING


def test_activity_with_all_fields():
    """Test creating an activity with all optional fields populated."""
    activity = Activity(
        activityId="test-456",
        startDateTimeLocal=datetime(2024, 10, 30, 8, 0, 0, tzinfo=timezone.utc),
        distance=10.5,
        duration=3600,
        activityType="running",
        cadenceAverage=170.5,
        cadenceMin=160.0,
        cadenceMax=185.0,
        heartRateAverage=145.0,
        heartRateMin=120.0,
        heartRateMax=165.0,
        bodyWeight=70.5,
        howFelt="great",
        terrain="road",
        temperature=15,
        weatherType="clear",
        humidity=60,
        windSpeed=10,
        notes="Great morning run!",
    )

    assert activity.activity_id == "test-456"
    assert activity.distance == 10.5
    assert activity.cadence_average == 170.5
    assert activity.heart_rate_average == 145.0
    assert activity.how_felt == HowFelt.GREAT
    assert activity.terrain == Terrain.ROAD
    assert activity.weather_type == WeatherType.CLEAR
    assert activity.notes == "Great morning run!"


def test_activity_computed_properties():
    """Test computed pace and speed properties."""
    # 5 km in 30 minutes (1800 seconds)
    activity = Activity(
        activityId="test-789",
        startDateTimeLocal=datetime.now(timezone.utc),
        distance=5.0,
        duration=1800,
    )

    # Average pace should be 6:00 min/km
    assert activity.average_pace_min_per_km == pytest.approx(6.0, rel=0.01)

    # Average speed should be 10 kph
    assert activity.average_speed_kph == pytest.approx(10.0, rel=0.01)


def test_activity_validation_distance():
    """Test that distance must be positive."""
    with pytest.raises(ValueError):
        Activity(
            activityId="test-invalid",
            startDateTimeLocal=datetime.now(timezone.utc),
            distance=0,  # Invalid: must be > 0
            duration=1800,
        )


def test_activity_validation_duration():
    """Test that duration must be positive."""
    with pytest.raises(ValueError):
        Activity(
            activityId="test-invalid",
            startDateTimeLocal=datetime.now(timezone.utc),
            distance=5.0,
            duration=0,  # Invalid: must be > 0
        )


def test_activity_with_recording_data():
    """Test activity with time series recording data."""
    activity = Activity(
        activityId="test-recording",
        startDateTimeLocal=datetime.now(timezone.utc),
        distance=5.0,
        duration=1800,
        recordingKeys=["clock", "distance", "heartRate"],
        recordingValues=[
            [0.0, 100.0, 200.0],  # clock values
            [0.0, 0.5, 1.0],  # distance values
            [120.0, 145.0, 150.0],  # heart rate values
        ],
    )

    assert activity.recording_keys is not None
    assert len(activity.recording_keys) == 3
    assert activity.recording_values is not None
    assert len(activity.recording_values) == 3


def test_activity_recording_data_validation():
    """Test that recording_values length must match recording_keys length."""
    with pytest.raises(ValueError, match="recording_values length"):
        Activity(
            activityId="test-invalid",
            startDateTimeLocal=datetime.now(timezone.utc),
            distance=5.0,
            duration=1800,
            recordingKeys=["clock", "distance"],
            recordingValues=[[0.0, 100.0, 200.0]],  # Length mismatch!
        )


def test_lap_model():
    """Test Lap nested model."""
    lap = Lap(
        lapType="work",
        endTime=300.0,
        endDistance=1000.0,
    )

    assert lap.lap_type == LapType.WORK
    assert lap.end_time == 300.0
    assert lap.end_distance == 1000.0


def test_song_model():
    """Test Song nested model."""
    song = Song(
        album="Greatest Hits",
        artist="Test Artist",
        song="Test Song",
        BPM=120,
        startClock=0.0,
        endClock=180.0,
    )

    assert song.album == "Greatest Hits"
    assert song.artist == "Test Artist"
    assert song.song == "Test Song"
    assert song.bpm == 120
    assert song.start_clock == 0.0
    assert song.end_clock == 180.0


def test_heart_rate_recovery_model():
    """Test HeartRateRecovery nested model."""
    hrr = HeartRateRecovery(
        duration=60,
        heartRate=100.0,
    )

    assert hrr.duration == 60
    assert hrr.heart_rate == 100.0


def test_activity_with_nested_objects():
    """Test activity with laps, songs, and heart rate recovery."""
    activity = Activity(
        activityId="test-nested",
        startDateTimeLocal=datetime.now(timezone.utc),
        distance=10.0,
        duration=3600,
        laps=[
            Lap(lapType="warmup", endTime=600.0),
            Lap(lapType="work", endDistance=5000.0),
            Lap(lapType="cooldown", endTime=3600.0),
        ],
        songs=[
            Song(
                song="Song 1",
                artist="Artist 1",
                startClock=0.0,
                endClock=200.0,
            ),
        ],
        heartRateRecovery=[
            HeartRateRecovery(duration=60, heartRate=120.0),
            HeartRateRecovery(duration=120, heartRate=100.0),
        ],
    )

    assert activity.laps is not None
    assert len(activity.laps) == 3
    assert activity.laps[0].lap_type == LapType.WARMUP

    assert activity.songs is not None
    assert len(activity.songs) == 1

    assert activity.heart_rate_recovery is not None
    assert len(activity.heart_rate_recovery) == 2


def test_activity_alias_support():
    """Test that both snake_case and camelCase field names work."""
    # Using snake_case
    activity1 = Activity(
        activity_id="test-1",
        start_date_time_local=datetime.now(timezone.utc),
        distance=5.0,
        duration=1800,
        cadence_average=170.0,
    )

    # Using camelCase (API format)
    activity2 = Activity(
        activityId="test-2",
        startDateTimeLocal=datetime.now(timezone.utc),
        distance=5.0,
        duration=1800,
        cadenceAverage=170.0,
    )

    # Both should work and produce same result
    assert activity1.activity_id == "test-1"
    assert activity2.activity_id == "test-2"
    assert activity1.cadence_average == activity2.cadence_average
