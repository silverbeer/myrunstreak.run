"""Activity-file import: parse GPX / TCX / SmashRun JSON into an ``Activity`` (SB-99).

One parser per format, all funnelling into the same canonical model the
SmashRun sync already produces — so imported runs are stored, deduped and
displayed exactly like synced ones.
"""

from .dispatch import (
    ALLOWED_EXTENSIONS,
    DEFAULT_TIMEZONE,
    MAX_UPLOAD_BYTES,
    parse_activity_file,
)
from .errors import (
    ActivityParseError,
    FileTooLargeError,
    NoRunFoundError,
    UnsupportedFileError,
)
from .gpx import parse_gpx
from .models import ParsedActivityFile
from .smashrun_json import parse_smashrun_json
from .tcx import parse_tcx

__all__ = [
    "ALLOWED_EXTENSIONS",
    "DEFAULT_TIMEZONE",
    "MAX_UPLOAD_BYTES",
    "ActivityParseError",
    "FileTooLargeError",
    "NoRunFoundError",
    "ParsedActivityFile",
    "UnsupportedFileError",
    "parse_activity_file",
    "parse_gpx",
    "parse_smashrun_json",
    "parse_tcx",
]
