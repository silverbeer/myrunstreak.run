"""SmashRun export JSON parser (SB-99).

SmashRun's export is the same shape its API returns, which is the shape the
``Activity`` model already speaks — so this parser is mostly validation plus
pulling the GPS track out of the parallel ``recordingKeys`` /
``recordingValues`` arrays.
"""

from __future__ import annotations

import json
from typing import Any

from src.shared.models import Activity

from .errors import ActivityParseError, NoRunFoundError
from .models import ParsedActivityFile


def _extract_track(payload: dict[str, Any]) -> tuple[list[float], list[float]]:
    """Latitude/longitude series out of the recording arrays, if present."""
    keys = payload.get("recordingKeys")
    values = payload.get("recordingValues")
    if not isinstance(keys, list) or not isinstance(values, list):
        return [], []
    if "latitude" not in keys or "longitude" not in keys:
        return [], []

    lat_index, lon_index = keys.index("latitude"), keys.index("longitude")
    if lat_index >= len(values) or lon_index >= len(values):
        return [], []

    lats = [float(v) for v in values[lat_index]]
    lons = [float(v) for v in values[lon_index]]
    # A truncated export can leave the series ragged; the shorter one wins
    # rather than failing the whole import over a few trailing fixes.
    size = min(len(lats), len(lons))
    return lats[:size], lons[:size]


def parse_smashrun_json(content: bytes) -> ParsedActivityFile:
    """Parse a SmashRun activity JSON export into a ParsedActivityFile.

    Raises:
        ActivityParseError: not valid JSON, or not a single activity object.
        NoRunFoundError: the payload holds no activity.
    """
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ActivityParseError(f"File is not valid JSON: {exc}") from exc

    if isinstance(payload, list):
        if not payload:
            raise NoRunFoundError("The JSON file holds no activities.")
        if len(payload) > 1:
            raise ActivityParseError(
                f"This file holds {len(payload)} activities. "
                "Single-file import takes one run at a time."
            )
        payload = payload[0]

    if not isinstance(payload, dict):
        raise ActivityParseError("Expected a JSON object describing one activity.")

    try:
        activity = Activity.model_validate(payload)
    except Exception as exc:  # pydantic ValidationError, surfaced to the user
        raise ActivityParseError(f"Activity is missing required fields: {exc}") from exc

    lats, lons = _extract_track(payload)
    # Re-key so an imported run can never collide with the same activity
    # arriving later over the SmashRun OAuth sync, which owns the bare id.
    activity = activity.model_copy(update={"activity_id": f"smashrun-{activity.activity_id}"})
    return ParsedActivityFile(
        activity=activity,
        latitudes=lats,
        longitudes=lons,
        times_are_utc=False,  # startDateTimeLocal is already local, with offset
    )
