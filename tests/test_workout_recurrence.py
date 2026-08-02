"""SB-535: which days a weekly pattern owes, and from when.

The walk is the whole risk in recurrence, so it is tested without a database.
The property everything else rests on: generation moves forward only. A skipped
Thursday is never regenerated, and that is what lets one occasion be deleted
without cancelling the pattern behind it.
"""

from __future__ import annotations

from datetime import date

from src.shared.workout_recurrence import DEFAULT_HORIZON_DAYS, due_dates, js_weekday

# 2026-08-03 is a Monday.
MON = date(2026, 8, 3)
THU = date(2026, 8, 6)


def test_js_weekday_matches_the_javascript_convention():
    """0 = Sunday, because the UI produces these values."""
    assert js_weekday(date(2026, 8, 2)) == 0  # Sunday
    assert js_weekday(MON) == 1
    assert js_weekday(THU) == 4
    assert js_weekday(date(2026, 8, 8)) == 6  # Saturday


def test_expands_a_weekly_pattern_into_dates():
    days = due_dates(
        byweekday=[1, 4],  # Monday + Thursday
        starts_on=MON,
        ends_on=None,
        generated_through=None,
        today=MON,
        horizon_days=14,
    )
    assert days == [
        date(2026, 8, 3),
        date(2026, 8, 6),
        date(2026, 8, 10),
        date(2026, 8, 13),
        date(2026, 8, 17),
    ]


def test_never_generates_the_same_day_twice():
    """The watermark is the whole mechanism: a second pass owes nothing."""
    first = due_dates(
        byweekday=[1],
        starts_on=MON,
        ends_on=None,
        generated_through=None,
        today=MON,
        horizon_days=14,
    )
    again = due_dates(
        byweekday=[1],
        starts_on=MON,
        ends_on=None,
        generated_through=max(first),
        today=MON,
        horizon_days=14,
    )
    assert first
    assert again == []


def test_a_skipped_occasion_is_not_regenerated():
    """Delete one Thursday and the rule keeps producing every Thursday after it
    — the thing recurring calendars are always asked for."""
    # The rule has already generated through 2026-08-20; the athlete deleted the
    # 13th. The next pass must pick up after the watermark, not fill the hole.
    days = due_dates(
        byweekday=[4],
        starts_on=MON,
        ends_on=None,
        generated_through=date(2026, 8, 20),
        today=MON,
        horizon_days=28,
    )
    assert date(2026, 8, 13) not in days
    assert days == [date(2026, 8, 27)]


def test_does_not_backfill_the_past():
    """A rule added mid-season owes nothing for the days it "should" have
    produced — those already went by."""
    days = due_dates(
        byweekday=[1],
        starts_on=date(2026, 6, 1),
        ends_on=None,
        generated_through=None,
        today=MON,
        horizon_days=7,
    )
    assert all(d >= MON for d in days)
    assert days == [date(2026, 8, 3), date(2026, 8, 10)]


def test_stops_at_an_end_date():
    days = due_dates(
        byweekday=[1, 4],
        starts_on=MON,
        ends_on=date(2026, 8, 10),
        generated_through=None,
        today=MON,
        horizon_days=28,
    )
    assert days == [date(2026, 8, 3), date(2026, 8, 6), date(2026, 8, 10)]


def test_an_ended_rule_owes_nothing():
    assert (
        due_dates(
            byweekday=[1],
            starts_on=date(2026, 6, 1),
            ends_on=date(2026, 7, 1),
            generated_through=None,
            today=MON,
            horizon_days=28,
        )
        == []
    )


def test_a_rule_that_starts_inside_the_window_begins_there():
    days = due_dates(
        byweekday=[1],
        starts_on=date(2026, 8, 10),
        ends_on=None,
        generated_through=None,
        today=MON,
        horizon_days=28,
    )
    assert days == [date(2026, 8, 10), date(2026, 8, 17), date(2026, 8, 24), date(2026, 8, 31)]


def test_a_rule_starting_beyond_the_horizon_owes_nothing_yet():
    """Not "never" — the window moves, and it will be picked up when it arrives.
    Materialising a season in advance is what the horizon exists to avoid."""
    days = due_dates(
        byweekday=[1],
        starts_on=date(2026, 9, 14),
        ends_on=None,
        generated_through=None,
        today=MON,
        horizon_days=28,
    )
    assert days == []


def test_no_days_selected_owes_nothing():
    assert (
        due_dates(
            byweekday=[],
            starts_on=MON,
            ends_on=None,
            generated_through=None,
            today=MON,
        )
        == []
    )


def test_the_horizon_bounds_how_far_ahead_it_materialises():
    """Four weeks: enough that Coming up is never empty, short enough that a
    changed rule is felt this month rather than next year."""
    days = due_dates(
        byweekday=[0, 1, 2, 3, 4, 5, 6],
        starts_on=MON,
        ends_on=None,
        generated_through=None,
        today=MON,
    )
    assert len(days) == DEFAULT_HORIZON_DAYS + 1
    assert max(days) == date(2026, 8, 31)
