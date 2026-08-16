"""TCX parser (SB-99).

Unlike GPX, TCX is an *activity* format: each lap states its own distance and
elapsed time, and the activity states an id and a sport. Those stated values
are trusted over anything derived from the trackpoints — the watch knows its
own wheel/stride calibration, and summing raw GPS fixes over-reads distance.
"""

from __future__ import annotations

import hashlib
from xml.etree.ElementTree import Element

from src.shared.geo import path_length_km
from src.shared.models import Activity

from .cadence import to_steps_per_minute
from .errors import NoRunFoundError
from .models import ParsedActivityFile
from .xml_common import (
    child_float,
    child_text,
    find_all,
    mean,
    parse_timestamp,
    parse_xml,
    recorded,
)

# TCX Sport attribute values we accept. Biking/Other files parse fine but are
# not runs, and the runs table is running-only (ActivityType has one member).
RUN_SPORTS = {"running", "run"}


def _track_series(
    activity_el: Element,
) -> tuple[
    list[float],
    list[float],
    list[float],
    list[float],
]:
    """(lats, lons, heart rates, cadences) across every trackpoint."""
    lats: list[float] = []
    lons: list[float] = []
    heart_rates: list[float] = []
    cadences: list[float] = []

    for point in find_all(activity_el, "Trackpoint"):
        lat = child_float(point, "LatitudeDegrees")
        lon = child_float(point, "LongitudeDegrees")
        if lat is not None and lon is not None:
            lats.append(lat)
            lons.append(lon)

        # <HeartRateBpm><Value>N</Value></HeartRateBpm> — the nested lookup
        # finds Value wherever the writer nested it.
        heart_rate = child_float(point, "HeartRateBpm")
        if heart_rate is None:
            hr_el = find_all(point, "HeartRateBpm")
            heart_rate = child_float(hr_el[0], "Value") if hr_el else None
        if heart_rate is not None:
            heart_rates.append(heart_rate)

        # Plain <Cadence>, or <Extensions><TPX><RunCadence> on Garmin.
        cadence = child_float(point, "Cadence")
        if cadence is None:
            cadence = child_float(point, "RunCadence")
        if cadence is not None:
            cadences.append(cadence)

    return lats, lons, heart_rates, cadences


def parse_tcx(content: bytes) -> ParsedActivityFile:
    """Parse TCX bytes into a ParsedActivityFile.

    Raises:
        ActivityParseError: file is not valid XML.
        NoRunFoundError: no activity, not a run, or zero distance/duration.
    """
    root = parse_xml(content)
    activities = find_all(root, "Activity")
    if not activities:
        raise NoRunFoundError("No activity found in the TCX file.")

    activity_el = activities[0]
    sport = (activity_el.get("Sport") or "").strip().lower()
    if sport and sport not in RUN_SPORTS:
        raise NoRunFoundError(f"This file is a {sport} activity, and only runs can be imported.")

    laps = find_all(activity_el, "Lap")
    distance_km = sum(child_float(lap, "DistanceMeters") or 0.0 for lap in laps) / 1000
    duration_seconds = sum(child_float(lap, "TotalTimeSeconds") or 0.0 for lap in laps)

    lats, lons, heart_rates, cadences = _track_series(activity_el)
    # A 0 sample means the watch had nothing to report, not a real reading.
    heart_rates, cadences = recorded(heart_rates), recorded(cadences)

    # Some exporters write laps without distance; fall back to the track.
    if distance_km <= 0 and len(lats) >= 2:
        distance_km = path_length_km(list(zip(lats, lons, strict=True)))

    if distance_km <= 0 or duration_seconds <= 0:
        raise NoRunFoundError("Activity states no distance or no elapsed time.")

    started = parse_timestamp(child_text(activity_el, "Id")) or parse_timestamp(
        child_text(activity_el, "Time")
    )
    if started is None:
        raise NoRunFoundError("Activity has no start time.")

    # <Id> is TCX's activity identifier (the start timestamp, per the schema).
    # It is stable across re-exports of the same run, which makes it a better
    # dedup key than the file bytes — those change when the exporter changes.
    raw_id = child_text(activity_el, "Id")
    identity = raw_id or hashlib.sha256(content).hexdigest()[:24]

    # Garmin writes running cadence as strides per minute in both <Cadence> and
    # <RunCadence>; the runs table stores steps per minute (SB-623).
    cadence_avg, cadence_min, cadence_max = to_steps_per_minute(
        mean(cadences),
        min(cadences) if cadences else None,
        max(cadences) if cadences else None,
    )

    activity = Activity(
        activityId=f"tcx-{identity}",
        startDateTimeLocal=started,
        distance=distance_km,
        duration=duration_seconds,
        startLatitude=lats[0] if lats else None,
        startLongitude=lons[0] if lons else None,
        hasDetailsGPS=len(lats) >= 2,
        isTreadmill=not lats,
        heartRateAverage=mean(heart_rates),
        heartRateMin=min(heart_rates) if heart_rates else None,
        heartRateMax=max(heart_rates) if heart_rates else None,
        cadenceAverage=cadence_avg,
        cadenceMin=cadence_min,
        cadenceMax=cadence_max,
    )
    return ParsedActivityFile(activity=activity, latitudes=lats, longitudes=lons)
