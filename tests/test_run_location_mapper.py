"""SB-290: activity_to_run_dict captures start location + a correct GPS flag."""

from datetime import UTC, datetime
from uuid import uuid4

from src.shared.models import Activity
from src.shared.supabase_ops.mappers import activity_to_run_dict

USER = uuid4()
SOURCE = uuid4()


def _run_dict(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "activityId": "act-loc-1",
        "startDateTimeLocal": datetime(2026, 7, 21, 8, 32, 0, tzinfo=UTC),
        "distance": 6.88,
        "duration": 2498,
    }
    payload.update(overrides)
    return activity_to_run_dict(Activity(**payload), USER, SOURCE)


def test_outdoor_run_captures_start_coords_and_gps_flag() -> None:
    out = _run_dict(
        startLatitude=42.2626,
        startLongitude=-71.8023,
        hasDetailsGPS=True,
        isTreadmill=False,
    )
    assert out["start_latitude"] == 42.2626
    assert out["start_longitude"] == -71.8023
    assert out["is_treadmill"] is False
    # has_gps_data now tracks SmashRun's hasDetailsGPS, not recording_keys.
    assert out["has_gps_data"] is True


def test_treadmill_run_has_no_coords_and_no_gps() -> None:
    out = _run_dict(hasDetailsGPS=False, isTreadmill=True)
    assert out["start_latitude"] is None
    assert out["start_longitude"] is None
    assert out["is_treadmill"] is True
    assert out["has_gps_data"] is False


def test_gps_flag_ignores_recording_keys() -> None:
    # Regression: the old derivation set has_gps_data from recording_keys, which
    # the list payload never carries. It must follow hasDetailsGPS instead.
    out = _run_dict(hasDetailsGPS=True, recordingKeys=None)
    assert out["has_gps_data"] is True

    out2 = _run_dict(hasDetailsGPS=False, recordingKeys=["latitude", "longitude"])
    assert out2["has_gps_data"] is False


def test_fields_default_when_absent() -> None:
    out = _run_dict()  # no location fields in payload
    assert out["start_latitude"] is None
    assert out["start_longitude"] is None
    assert out["is_treadmill"] is False
    assert out["has_gps_data"] is False
