"""Entry point for activity-file import: pick a parser, enforce upload safety (SB-99).

The size cap and the extension allowlist are checked *before* any parsing, so a
200 MB or wrong-format upload is rejected without ever reaching an XML or JSON
decoder.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import PurePosixPath
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import ActivityParseError, FileTooLargeError, UnsupportedFileError
from .gpx import parse_gpx
from .models import ParsedActivityFile
from .smashrun_json import parse_smashrun_json
from .tcx import parse_tcx

# A GPX with per-second fixes runs ~100 KB/hour; 10 MB is a very long ultra with
# room to spare, while still bounding what one request can hold in memory.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# The timezone GPX/TCX timestamps are read into when the caller states none.
# Matches the default already used for streak/date boundaries elsewhere.
DEFAULT_TIMEZONE = "America/New_York"

PARSERS: dict[str, Callable[[bytes], ParsedActivityFile]] = {
    ".gpx": parse_gpx,
    ".tcx": parse_tcx,
    ".json": parse_smashrun_json,
}

ALLOWED_EXTENSIONS = tuple(sorted(PARSERS))


def _extension(filename: str) -> str:
    return PurePosixPath(filename.strip()).suffix.lower()


def parse_activity_file(
    filename: str,
    content: bytes,
    timezone: str = DEFAULT_TIMEZONE,
) -> ParsedActivityFile:
    """Parse one uploaded activity file.

    Args:
        filename: Original file name — only its extension is used, never as a path.
        content: Raw file bytes.
        timezone: IANA zone the run happened in; applied to formats that record
            in UTC so the run lands on the right local date.

    Returns:
        The parsed activity plus its GPS track, if any.

    Raises:
        UnsupportedFileError: extension not in the allowlist.
        FileTooLargeError: content exceeds MAX_UPLOAD_BYTES.
        ActivityParseError: unparseable file, unknown timezone, or no usable run.
    """
    extension = _extension(filename)
    parser = PARSERS.get(extension)
    if parser is None:
        allowed = ", ".join(ALLOWED_EXTENSIONS)
        raise UnsupportedFileError(
            f"{extension or 'This file'} can't be imported. Supported formats: {allowed}."
        )

    if len(content) > MAX_UPLOAD_BYTES:
        limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise FileTooLargeError(f"File is larger than the {limit_mb} MB limit.")
    if not content.strip():
        raise ActivityParseError("File is empty.")

    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ActivityParseError(f"Unknown timezone '{timezone}'.") from exc

    parsed = parser(content)
    if not parsed.times_are_utc:
        return parsed

    localized = parsed.activity.model_copy(
        update={"start_date_time_local": parsed.activity.start_date_time_local.astimezone(zone)}
    )
    return ParsedActivityFile(
        activity=localized,
        latitudes=parsed.latitudes,
        longitudes=parsed.longitudes,
        times_are_utc=False,
    )
