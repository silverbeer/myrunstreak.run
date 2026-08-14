"""GPX parser (SB-99).

GPX is a track format, not an activity format: it states where you were and
when, and nothing else. Distance and duration are therefore *derived* from the
trackpoints. Heart rate and cadence, when present, live in the Garmin
TrackPointExtension namespace that most watches and apps write.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from xml.etree.ElementTree import Element

from src.shared.geo import path_length_km
from src.shared.models import Activity

from .errors import NoRunFoundError
from .models import ParsedActivityFile
from .xml_common import child_text, find_all, mean, parse_timestamp, parse_xml

# GPS fixes 60s+ apart are a paused watch, not a slow kilometre. Elapsed time
# includes such gaps; the run's duration should not, so they are subtracted —
# this keeps an imported pace comparable with a SmashRun-synced one, whose
# duration already excludes pauses.
PAUSE_GAP_SECONDS = 60.0


def _trackpoints(root: Element) -> list[Element]:
    return find_all(root, "trkpt")


def _point_values(
    points: list[Element],
) -> tuple[
    list[float],
    list[float],
    list[datetime],
    list[float],
    list[float],
]:
    """(lats, lons, times, heart rates, cadences) — each list only as long as
    the data actually present, since a fix may carry coordinates but no HR."""
    lats: list[float] = []
    lons: list[float] = []
    times: list[datetime] = []
    heart_rates: list[float] = []
    cadences: list[float] = []

    for point in points:
        lat, lon = point.get("lat"), point.get("lon")
        if lat is None or lon is None:
            continue
        try:
            lats.append(float(lat))
            lons.append(float(lon))
        except ValueError:
            continue

        when = parse_timestamp(child_text(point, "time"))
        if when is not None:
            times.append(when)

        # TrackPointExtension: <gpxtpx:hr>, <gpxtpx:cad>. Namespace-agnostic
        # lookup — Garmin, Strava and Apple all write different URIs here.
        for name, sink in (("hr", heart_rates), ("cad", cadences)):
            raw = child_text(point, name)
            if raw is None:
                continue
            try:
                sink.append(float(raw))
            except ValueError:
                continue

    return lats, lons, times, heart_rates, cadences


def _moving_seconds(times: list[datetime]) -> float:
    """Elapsed time minus paused gaps."""
    total = 0.0
    for i in range(1, len(times)):
        gap = (times[i] - times[i - 1]).total_seconds()
        if 0 < gap <= PAUSE_GAP_SECONDS:
            total += gap
    return total


def parse_gpx(content: bytes) -> ParsedActivityFile:
    """Parse GPX bytes into a ParsedActivityFile.

    Raises:
        ActivityParseError: file is not valid XML.
        NoRunFoundError: no usable track (no points, no time, or zero distance).
    """
    root = parse_xml(content)
    points = _trackpoints(root)
    if not points:
        raise NoRunFoundError("No GPS trackpoints found — is this an empty or route-only GPX?")

    lats, lons, times, heart_rates, cadences = _point_values(points)
    if len(lats) < 2:
        raise NoRunFoundError("Track has fewer than two GPS points, so it has no distance.")
    if len(times) < 2:
        raise NoRunFoundError("Trackpoints carry no timestamps, so the run has no duration.")

    distance_km = path_length_km(list(zip(lats, lons, strict=True)))
    duration_seconds = _moving_seconds(times)
    if distance_km <= 0 or duration_seconds <= 0:
        raise NoRunFoundError("Track covers no distance or no time.")

    # GPX states no activity id of its own, so the file's own bytes are the
    # dedup key: re-uploading the same export is then a no-op, which is the
    # idempotency the endpoint promises.
    digest = hashlib.sha256(content).hexdigest()[:24]

    # <trk><name> is the run's title in most writers ("Morning Run"). It is a
    # label, not an identifier, so it lands in notes rather than external_id.
    track = find_all(root, "trk")
    title = child_text(track[0], "name") if track else None

    activity = Activity(
        activityId=f"gpx-{digest}",
        startDateTimeLocal=min(times),
        distance=distance_km,
        duration=duration_seconds,
        notes=title[:800] if title else None,
        startLatitude=lats[0],
        startLongitude=lons[0],
        hasDetailsGPS=True,
        heartRateAverage=mean(heart_rates),
        heartRateMin=min(heart_rates) if heart_rates else None,
        heartRateMax=max(heart_rates) if heart_rates else None,
        cadenceAverage=mean(cadences),
        cadenceMin=min(cadences) if cadences else None,
        cadenceMax=max(cadences) if cadences else None,
    )
    return ParsedActivityFile(activity=activity, latitudes=lats, longitudes=lons)
