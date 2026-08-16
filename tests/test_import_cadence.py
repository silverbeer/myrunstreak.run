"""SB-623: imported cadence is normalized from strides to steps per minute."""

from __future__ import annotations

import pytest

from src.shared.importers import parse_gpx, parse_tcx
from src.shared.importers.cadence import STRIDE_RATE_CEILING, to_steps_per_minute


def _gpx(cadences: list[int]) -> bytes:
    points = "\n".join(
        f"""      <trkpt lat="42.24{i:02d}" lon="-71.6500">
        <time>2026-08-10T11:{i:02d}:00Z</time>
        <extensions><gpxtpx:TrackPointExtension>
          <gpxtpx:cad>{c}</gpxtpx:cad>
        </gpxtpx:TrackPointExtension></extensions>
      </trkpt>"""
        for i, c in enumerate(cadences)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Test" xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">
  <trk><name>Test</name><trkseg>
{points}
  </trkseg></trk>
</gpx>
""".encode()


def _tcx(cadences: list[int]) -> bytes:
    points = "\n".join(
        f"""          <Trackpoint>
            <Time>2026-08-10T12:{i:02d}:00Z</Time>
            <Position>
              <LatitudeDegrees>42.24{i:02d}</LatitudeDegrees>
              <LongitudeDegrees>-71.6500</LongitudeDegrees>
            </Position>
            <Cadence>{c}</Cadence>
          </Trackpoint>"""
        for i, c in enumerate(cadences)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Activities><Activity Sport="Running">
      <Id>2026-08-10T12:00:00Z</Id>
      <Lap StartTime="2026-08-10T12:00:00Z">
        <TotalTimeSeconds>1800</TotalTimeSeconds>
        <DistanceMeters>5000</DistanceMeters>
        <Track>
{points}
        </Track>
      </Lap>
  </Activity></Activities>
</TrainingCenterDatabase>
""".encode()


# --- the helper ------------------------------------------------------------


def test_stride_rate_is_doubled() -> None:
    assert to_steps_per_minute(93.0, 80.0, 99.0) == (186.0, 160.0, 198.0)


def test_step_rate_is_left_alone() -> None:
    assert to_steps_per_minute(178.0, 160.0, 190.0) == (178.0, 160.0, 190.0)


def test_the_whole_triple_moves_together() -> None:
    # Deciding per value would leave a doubled average beside an untouched
    # maximum — worse than either unit applied consistently.
    average, minimum, maximum = to_steps_per_minute(95.0, 60.0, 129.0)
    assert (average, minimum, maximum) == (190.0, 120.0, 258.0)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (STRIDE_RATE_CEILING - 0.1, (STRIDE_RATE_CEILING - 0.1) * 2),
        (STRIDE_RATE_CEILING, STRIDE_RATE_CEILING),
        (STRIDE_RATE_CEILING + 0.1, STRIDE_RATE_CEILING + 0.1),
    ],
)
def test_the_boundary_is_exclusive(value: float, expected: float) -> None:
    assert to_steps_per_minute(value, None, None)[0] == pytest.approx(expected)


def test_absent_cadence_stays_absent() -> None:
    assert to_steps_per_minute(None, None, None) == (None, None, None)


def test_zero_is_not_doubled() -> None:
    # A watch that reported nothing shouldn't become a run with 0 cadence
    # "corrected" to 0 — and shouldn't crash on the way through either.
    assert to_steps_per_minute(0.0, 0.0, 0.0) == (0.0, 0.0, 0.0)


def test_missing_bounds_survive_the_correction() -> None:
    assert to_steps_per_minute(90.0, None, None) == (180.0, None, None)


# --- through the parsers ---------------------------------------------------


def test_gpx_stride_cadence_becomes_steps() -> None:
    # A real Garmin export reads ~93 for a normal running cadence.
    activity = parse_gpx(_gpx([90, 93, 96])).activity
    assert activity.cadence_average == pytest.approx(186.0)
    assert activity.cadence_min == 180
    assert activity.cadence_max == 192


def test_gpx_step_cadence_is_untouched() -> None:
    activity = parse_gpx(_gpx([176, 180, 184])).activity
    assert activity.cadence_average == pytest.approx(180.0)
    assert activity.cadence_max == 184


def test_tcx_stride_cadence_becomes_steps() -> None:
    activity = parse_tcx(_tcx([86, 90, 94])).activity
    assert activity.cadence_average == pytest.approx(180.0)
    assert activity.cadence_min == 172


def test_tcx_step_cadence_is_untouched() -> None:
    activity = parse_tcx(_tcx([170, 178, 186])).activity
    assert activity.cadence_average == pytest.approx(178.0)


def test_zero_samples_do_not_become_the_minimum() -> None:
    # A watch writes 0 while stopped. Kept in, "minimum cadence" reads 0 on
    # every run that ever paused, and the average sits below what was held.
    activity = parse_gpx(_gpx([0, 90, 96, 0])).activity
    assert activity.cadence_min == 180
    assert activity.cadence_average == pytest.approx(186.0)


def test_zero_samples_are_dropped_from_tcx_too() -> None:
    activity = parse_tcx(_tcx([0, 86, 94])).activity
    assert activity.cadence_min == 172
    assert activity.cadence_average == pytest.approx(180.0)


def test_an_all_zero_series_reads_as_no_cadence() -> None:
    activity = parse_gpx(_gpx([0, 0, 0])).activity
    assert activity.cadence_average is None
    assert activity.cadence_min is None


def test_a_file_without_cadence_is_unaffected() -> None:
    no_cadence = (
        _gpx([90, 93])
        .replace(b"<gpxtpx:cad>90</gpxtpx:cad>", b"")
        .replace(b"<gpxtpx:cad>93</gpxtpx:cad>", b"")
    )
    activity = parse_gpx(no_cadence).activity
    assert activity.cadence_average is None
    assert activity.cadence_min is None
