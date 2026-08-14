"""What a parsed activity file yields (SB-99)."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.shared.models import Activity


@dataclass(frozen=True)
class ParsedActivityFile:
    """One activity file, normalized.

    ``activity`` is the canonical model every source already funnels into, so
    the import path reuses ``activity_to_run_dict`` + ``upsert_run`` unchanged.
    ``latitudes``/``longitudes`` carry the GPS track when the file has one —
    stored separately in ``run_tracks``, exactly as the SmashRun sync does.
    """

    activity: Activity
    latitudes: list[float] = field(default_factory=list)
    longitudes: list[float] = field(default_factory=list)
    # GPX and TCX record in UTC, so their timestamps have to be moved into the
    # runner's zone before the run's *date* is taken — a 9pm run would
    # otherwise land on tomorrow and break the streak. SmashRun's export
    # already states local time with an offset, and must be left alone.
    times_are_utc: bool = True

    @property
    def has_track(self) -> bool:
        return len(self.latitudes) >= 2 and len(self.latitudes) == len(self.longitudes)
