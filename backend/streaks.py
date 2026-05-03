"""Pure streak computation — no I/O, fully unit-testable.

Given a set of dates the user ran, walks them to identify every
maximal run of consecutive days and tags whichever one (if any)
is still active today.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Streak:
    start_date: date
    end_date: date
    length_days: int
    is_current: bool


def compute_streaks(run_dates: Iterable[date], today: date) -> list[Streak]:
    """Group run_dates into maximal consecutive-day windows.

    A streak is ``is_current`` if its end_date is ``today`` or ``today - 1``.
    The "yesterday" allowance matches get_current_streak's behavior so the
    user doesn't see "Current: 0" before they've had a chance to run today.

    Returns the streaks sorted descending by length, then by end_date.
    """
    unique = sorted(set(run_dates))
    if not unique:
        return []

    streaks: list[Streak] = []
    start = unique[0]
    prev = unique[0]

    for d in unique[1:]:
        if d == prev + timedelta(days=1):
            prev = d
            continue
        streaks.append(_make(start, prev, today))
        start = d
        prev = d
    streaks.append(_make(start, prev, today))

    streaks.sort(key=lambda s: (-s.length_days, -s.end_date.toordinal()))
    return streaks


def _make(start: date, end: date, today: date) -> Streak:
    length = (end - start).days + 1
    is_current = end == today or end == today - timedelta(days=1)
    return Streak(start_date=start, end_date=end, length_days=length, is_current=is_current)
