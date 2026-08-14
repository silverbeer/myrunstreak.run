"""Errors raised while parsing an uploaded activity file (SB-99).

Every message here is user-facing: it is returned verbatim by the import
endpoint, so it must say what is wrong with *their* file, not what went wrong
inside the parser.
"""

from __future__ import annotations


class ActivityParseError(ValueError):
    """The file could not be turned into an activity."""


class UnsupportedFileError(ActivityParseError):
    """The file's extension is not one we can parse."""


class FileTooLargeError(ActivityParseError):
    """The upload exceeds the size cap."""


class NoRunFoundError(ActivityParseError):
    """The file parsed, but holds no runnable activity (empty, or not a run)."""
