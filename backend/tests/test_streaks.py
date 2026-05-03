"""Tests for streak computation."""

from datetime import date

from backend.streaks import compute_streaks

TODAY = date(2026, 5, 3)


class TestComputeStreaks:
    def test_empty(self) -> None:
        assert compute_streaks([], TODAY) == []

    def test_single_day(self) -> None:
        s = compute_streaks([TODAY], TODAY)
        assert len(s) == 1
        assert s[0].length_days == 1
        assert s[0].is_current is True

    def test_consecutive_days_one_streak(self) -> None:
        days = [date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3)]
        s = compute_streaks(days, TODAY)
        assert len(s) == 1
        assert s[0].length_days == 3
        assert s[0].start_date == date(2026, 5, 1)
        assert s[0].end_date == date(2026, 5, 3)
        assert s[0].is_current is True

    def test_two_separate_streaks(self) -> None:
        days = [
            date(2026, 4, 1), date(2026, 4, 2), date(2026, 4, 3),  # 3-day
            date(2026, 5, 1), date(2026, 5, 2),  # 2-day, ending yesterday
        ]
        s = compute_streaks(days, TODAY)
        assert len(s) == 2
        assert s[0].length_days == 3
        assert s[0].is_current is False
        assert s[1].length_days == 2
        assert s[1].is_current is True  # yesterday counts

    def test_streak_ending_yesterday_is_current(self) -> None:
        days = [date(2026, 5, 1), date(2026, 5, 2)]  # 2-day, ends yesterday
        s = compute_streaks(days, TODAY)
        assert s[0].is_current is True

    def test_streak_ending_two_days_ago_is_not_current(self) -> None:
        days = [date(2026, 5, 1)]  # ends 2 days ago
        s = compute_streaks(days, TODAY)
        assert s[0].is_current is False

    def test_dedupes_same_day_runs(self) -> None:
        days = [date(2026, 5, 1), date(2026, 5, 1), date(2026, 5, 2)]
        s = compute_streaks(days, TODAY)
        assert len(s) == 1
        assert s[0].length_days == 2  # not 3

    def test_unsorted_input(self) -> None:
        days = [date(2026, 5, 3), date(2026, 5, 1), date(2026, 5, 2)]
        s = compute_streaks(days, TODAY)
        assert len(s) == 1
        assert s[0].length_days == 3

    def test_sorted_descending_by_length(self) -> None:
        days = [
            date(2026, 1, 1), date(2026, 1, 2),  # 2-day (older)
            date(2026, 4, 1), date(2026, 4, 2), date(2026, 4, 3),  # 3-day
            date(2026, 5, 3),  # 1-day, today
        ]
        s = compute_streaks(days, TODAY)
        assert [x.length_days for x in s] == [3, 2, 1]

    def test_long_streak(self) -> None:
        # 100-day streak ending today
        days = [date(2026, 5, 3) - __import__("datetime").timedelta(days=i) for i in range(100)]
        s = compute_streaks(days, TODAY)
        assert len(s) == 1
        assert s[0].length_days == 100
        assert s[0].is_current is True

    def test_gap_of_one_day_breaks_streak(self) -> None:
        days = [
            date(2026, 5, 1), date(2026, 5, 2),  # 2-day
            # missing 5/3
            date(2026, 5, 4),  # 1-day
        ]
        s = compute_streaks(days, date(2026, 5, 4))
        assert len(s) == 2
        assert s[0].length_days == 2
        assert s[1].length_days == 1
