"""SB-99: GPX / TCX / SmashRun-JSON parsers for single-file activity import."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from src.shared.importers import (
    ActivityParseError,
    FileTooLargeError,
    NoRunFoundError,
    UnsupportedFileError,
    parse_activity_file,
    parse_gpx,
    parse_smashrun_json,
    parse_tcx,
)
from src.shared.importers.dispatch import MAX_UPLOAD_BYTES

# Four fixes ~ 111 m apart in latitude, one minute between each.
GPX = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Test" xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">
  <metadata><name>export</name></metadata>
  <trk>
    <name>Evening Run</name>
    <trkseg>
      <trkpt lat="42.2400" lon="-71.6500">
        <ele>10</ele><time>2026-08-10T23:30:00Z</time>
        <extensions><gpxtpx:TrackPointExtension>
          <gpxtpx:hr>140</gpxtpx:hr><gpxtpx:cad>85</gpxtpx:cad>
        </gpxtpx:TrackPointExtension></extensions>
      </trkpt>
      <trkpt lat="42.2410" lon="-71.6500">
        <ele>11</ele><time>2026-08-10T23:31:00Z</time>
        <extensions><gpxtpx:TrackPointExtension>
          <gpxtpx:hr>150</gpxtpx:hr><gpxtpx:cad>88</gpxtpx:cad>
        </gpxtpx:TrackPointExtension></extensions>
      </trkpt>
      <trkpt lat="42.2420" lon="-71.6500">
        <ele>12</ele><time>2026-08-10T23:32:00Z</time>
        <extensions><gpxtpx:TrackPointExtension>
          <gpxtpx:hr>160</gpxtpx:hr><gpxtpx:cad>90</gpxtpx:cad>
        </gpxtpx:TrackPointExtension></extensions>
      </trkpt>
    </trkseg>
  </trk>
</gpx>
"""

TCX = b"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Activities>
    <Activity Sport="Running">
      <Id>2026-08-10T12:00:00Z</Id>
      <Lap StartTime="2026-08-10T12:00:00Z">
        <TotalTimeSeconds>1800</TotalTimeSeconds>
        <DistanceMeters>5000</DistanceMeters>
        <Track>
          <Trackpoint>
            <Time>2026-08-10T12:00:00Z</Time>
            <Position>
              <LatitudeDegrees>42.2400</LatitudeDegrees>
              <LongitudeDegrees>-71.6500</LongitudeDegrees>
            </Position>
            <HeartRateBpm><Value>142</Value></HeartRateBpm>
            <Cadence>86</Cadence>
          </Trackpoint>
          <Trackpoint>
            <Time>2026-08-10T12:15:00Z</Time>
            <Position>
              <LatitudeDegrees>42.2500</LatitudeDegrees>
              <LongitudeDegrees>-71.6500</LongitudeDegrees>
            </Position>
            <HeartRateBpm><Value>158</Value></HeartRateBpm>
            <Cadence>90</Cadence>
          </Trackpoint>
        </Track>
      </Lap>
    </Activity>
  </Activities>
</TrainingCenterDatabase>
"""

SMASHRUN = {
    "activityId": 987654,
    "startDateTimeLocal": "2026-08-10T07:15:00-04:00",
    "distance": 8.05,
    "duration": 2700.0,
    "heartRateAverage": 152,
    "recordingKeys": ["latitude", "longitude"],
    "recordingValues": [[42.24, 42.25, 42.26], [-71.65, -71.66, -71.67]],
}


# --- GPX -------------------------------------------------------------------


def test_gpx_derives_distance_and_duration_from_track() -> None:
    parsed = parse_gpx(GPX)
    # Two hops of 0.001 deg latitude ~= 111 m each.
    assert parsed.activity.distance == pytest.approx(0.222, abs=0.01)
    assert parsed.activity.duration == 120.0
    assert parsed.activity.start_date_time_local == datetime(2026, 8, 10, 23, 30, tzinfo=UTC)


def test_gpx_keeps_the_gps_track_and_hr_cadence() -> None:
    parsed = parse_gpx(GPX)
    assert parsed.has_track is True
    assert parsed.latitudes == [42.2400, 42.2410, 42.2420]
    assert parsed.activity.start_latitude == 42.2400
    assert parsed.activity.heart_rate_average == pytest.approx(150.0)
    assert parsed.activity.heart_rate_max == 160
    assert parsed.activity.cadence_average == pytest.approx(87.667, abs=0.01)
    assert parsed.activity.has_details_gps is True


def test_gpx_uses_track_name_as_notes() -> None:
    # <metadata><name> is "export"; the run's title lives on <trk>.
    assert parse_gpx(GPX).activity.notes == "Evening Run"


def test_gpx_dedup_key_is_stable_for_identical_bytes() -> None:
    assert parse_gpx(GPX).activity.activity_id == parse_gpx(GPX).activity.activity_id
    assert parse_gpx(GPX).activity.activity_id.startswith("gpx-")


def test_gpx_dedup_key_differs_for_different_files() -> None:
    other = GPX.replace(b"42.2420", b"42.2430")
    assert parse_gpx(GPX).activity.activity_id != parse_gpx(other).activity.activity_id


def test_gpx_excludes_paused_gaps_from_duration() -> None:
    # Push the last fix 20 minutes out: a stopped watch, not a slow kilometre.
    paused = GPX.replace(b"2026-08-10T23:32:00Z", b"2026-08-10T23:52:00Z")
    assert parse_gpx(paused).activity.duration == 60.0


def test_gpx_without_timestamps_is_rejected() -> None:
    timeless = GPX.replace(b"<time>2026-08-10T23:30:00Z</time>", b"").replace(
        b"<time>2026-08-10T23:31:00Z</time>", b""
    )
    with pytest.raises(NoRunFoundError, match="no timestamps"):
        parse_gpx(timeless)


def test_gpx_route_only_file_is_rejected() -> None:
    route_only = b"""<?xml version="1.0"?>
    <gpx xmlns="http://www.topografix.com/GPX/1/1">
      <rte><rtept lat="42.2" lon="-71.6"/></rte>
    </gpx>"""
    with pytest.raises(NoRunFoundError, match="No GPS trackpoints"):
        parse_gpx(route_only)


def test_malformed_xml_reports_a_usable_error() -> None:
    with pytest.raises(ActivityParseError, match="not valid XML"):
        parse_gpx(b"<gpx><trk>")


def test_entity_bomb_is_refused_not_expanded() -> None:
    # defusedxml refuses the DTD outright; xml.etree would try to expand it.
    bomb = b"""<?xml version="1.0"?>
    <!DOCTYPE gpx [
      <!ENTITY a "aaaaaaaaaa">
      <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
    ]>
    <gpx><trk><trkseg><trkpt lat="1" lon="1"><name>&b;</name></trkpt></trkseg></trk></gpx>"""
    with pytest.raises(Exception) as err:  # noqa: B017 - defusedxml raises its own type
        parse_gpx(bomb)
    assert "Entit" in str(type(err.value).__name__) or "not valid XML" in str(err.value)


# --- TCX -------------------------------------------------------------------


def test_tcx_trusts_the_stated_lap_totals_over_the_track() -> None:
    parsed = parse_tcx(TCX)
    # Track spans ~1.1 km; the lap states 5 km, and the lap wins.
    assert parsed.activity.distance == 5.0
    assert parsed.activity.duration == 1800.0


def test_tcx_uses_the_activity_id_as_dedup_key() -> None:
    parsed = parse_tcx(TCX)
    assert parsed.activity.activity_id == "tcx-2026-08-10T12:00:00Z"
    # Re-exported with a different creator, same run -> same key.
    reexported = TCX.replace(b'Sport="Running"', b'Sport="Running" Creator="Other"')
    assert parse_tcx(reexported).activity.activity_id == parsed.activity.activity_id


def test_tcx_reads_heart_rate_and_cadence() -> None:
    parsed = parse_tcx(TCX)
    assert parsed.activity.heart_rate_average == pytest.approx(150.0)
    assert parsed.activity.heart_rate_min == 142
    assert parsed.activity.cadence_average == pytest.approx(88.0)


def test_tcx_falls_back_to_the_track_when_laps_state_no_distance() -> None:
    no_distance = TCX.replace(b"<DistanceMeters>5000</DistanceMeters>", b"")
    parsed = parse_tcx(no_distance)
    assert parsed.activity.distance == pytest.approx(1.11, abs=0.02)


def test_tcx_non_running_activity_is_rejected() -> None:
    biking = TCX.replace(b'Sport="Running"', b'Sport="Biking"')
    with pytest.raises(NoRunFoundError, match="only runs"):
        parse_tcx(biking)


def test_tcx_indoor_run_without_gps_is_marked_treadmill() -> None:
    indoor = TCX
    for tag in (b"LatitudeDegrees", b"LongitudeDegrees"):
        indoor = indoor.replace(b"<" + tag + b">", b"<Ignored>").replace(
            b"</" + tag + b">", b"</Ignored>"
        )
    parsed = parse_tcx(indoor)
    assert parsed.activity.is_treadmill is True
    assert parsed.activity.has_details_gps is False
    assert parsed.has_track is False


# --- SmashRun JSON ---------------------------------------------------------


def test_smashrun_json_maps_straight_onto_activity() -> None:
    parsed = parse_smashrun_json(json.dumps(SMASHRUN).encode())
    assert parsed.activity.activity_id == "smashrun-987654"
    assert parsed.activity.distance == 8.05
    assert parsed.activity.heart_rate_average == 152
    assert parsed.latitudes == [42.24, 42.25, 42.26]


def test_smashrun_json_accepts_a_single_element_list() -> None:
    parsed = parse_smashrun_json(json.dumps([SMASHRUN]).encode())
    assert parsed.activity.activity_id == "smashrun-987654"


def test_smashrun_json_rejects_a_multi_activity_export() -> None:
    with pytest.raises(ActivityParseError, match="one run at a time"):
        parse_smashrun_json(json.dumps([SMASHRUN, SMASHRUN]).encode())


def test_smashrun_json_missing_fields_names_the_problem() -> None:
    partial = {k: v for k, v in SMASHRUN.items() if k != "distance"}
    with pytest.raises(ActivityParseError, match="missing required fields"):
        parse_smashrun_json(json.dumps(partial).encode())


def test_invalid_json_reports_a_usable_error() -> None:
    with pytest.raises(ActivityParseError, match="not valid JSON"):
        parse_smashrun_json(b"{not json")


# --- dispatch: allowlist, size cap, timezone --------------------------------


def test_dispatch_routes_on_extension() -> None:
    assert parse_activity_file("run.gpx", GPX).activity.activity_id.startswith("gpx-")
    assert parse_activity_file("run.TCX", TCX).activity.activity_id.startswith("tcx-")
    parsed = parse_activity_file("run.json", json.dumps(SMASHRUN).encode())
    assert parsed.activity.activity_id.startswith("smashrun-")


def test_dispatch_rejects_unknown_extensions_before_parsing() -> None:
    with pytest.raises(UnsupportedFileError, match="Supported formats"):
        parse_activity_file("run.fit", b"whatever")


def test_dispatch_enforces_the_size_cap() -> None:
    with pytest.raises(FileTooLargeError, match="10 MB"):
        parse_activity_file("run.gpx", b"x" * (MAX_UPLOAD_BYTES + 1))


def test_dispatch_rejects_an_empty_file() -> None:
    with pytest.raises(ActivityParseError, match="empty"):
        parse_activity_file("run.gpx", b"   ")


def test_utc_timestamps_move_into_the_runners_timezone() -> None:
    # 23:30 UTC on the 10th is 19:30 on the 10th in New York — the date the
    # streak has to count, and the one a naive UTC read would push to the 11th.
    parsed = parse_activity_file("run.gpx", GPX, timezone="America/New_York")
    local = parsed.activity.start_date_time_local
    assert (local.hour, local.day) == (19, 10)
    assert parsed.times_are_utc is False


def test_smashrun_local_time_is_left_alone() -> None:
    parsed = parse_activity_file(
        "run.json", json.dumps(SMASHRUN).encode(), timezone="America/Los_Angeles"
    )
    # Already local with an offset; converting it would move the run 3 hours.
    assert parsed.activity.start_date_time_local.hour == 7


def test_unknown_timezone_is_reported() -> None:
    with pytest.raises(ActivityParseError, match="Unknown timezone"):
        parse_activity_file("run.gpx", GPX, timezone="Mars/Olympus_Mons")
