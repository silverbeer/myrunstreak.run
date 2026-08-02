"""Expanding a weekly pattern into dated occasions (SB-535).

Kept pure and free of the database on purpose: the interesting part is the
walk — which days a rule owes, and from when — and it is far easier to trust
when it can be tested without a client at all. The repository does the writing.
"""

from __future__ import annotations

from datetime import date, timedelta

# How far ahead occasions are materialised. Four weeks is enough that Coming up
# always has the next few sessions in it, and short enough that changing a rule
# is felt within the month rather than a year from now.
DEFAULT_HORIZON_DAYS = 28


def js_weekday(day: date) -> int:
    """0 = Sunday .. 6 = Saturday, the convention `byweekday` is stored in.

    Python's own `weekday()` is Monday-based; converting here, once, keeps the
    off-by-one from being re-derived at every call site.
    """
    return (day.weekday() + 1) % 7


def due_dates(
    *,
    byweekday: list[int],
    starts_on: date,
    ends_on: date | None,
    generated_through: date | None,
    today: date,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> list[date]:
    """The dates a rule still owes, in order.

    Generation moves forward only. It begins the day after `generated_through`
    (or at `starts_on` for a rule that has never run), and never before today —
    so a rule added mid-week does not backfill the days it "should" have
    produced, and a skipped occasion is never regenerated. That single property
    is what lets one Thursday be deleted without cancelling Thursdays.
    """
    if not byweekday:
        return []

    first = starts_on
    if generated_through is not None and generated_through >= first:
        first = generated_through + timedelta(days=1)
    # Backfilling the past would put workouts in Coming up that already went by.
    first = max(first, today)

    last = today + timedelta(days=horizon_days)
    if ends_on is not None and ends_on < last:
        last = ends_on
    if last < first:
        return []

    wanted = set(byweekday)
    out: list[date] = []
    day = first
    while day <= last:
        if js_weekday(day) in wanted:
            out.append(day)
        day += timedelta(days=1)
    return out


def horizon_end(today: date, horizon_days: int = DEFAULT_HORIZON_DAYS) -> date:
    """The far edge of the materialisation window, for the watermark."""
    return today + timedelta(days=horizon_days)
