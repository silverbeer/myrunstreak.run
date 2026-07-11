"""Tests for workout display helpers — goal ranges, segments, goal-vs-reality (SB-264)."""

from __future__ import annotations

from cli.commands.workout import _fmt_distance, _fmt_goal, _fmt_secs, _fmt_target, _goal_status


def test_fmt_secs_compact_and_minutes() -> None:
    assert _fmt_secs(14) == "14s"
    assert _fmt_secs(31.0) == "31s"
    assert _fmt_secs(100) == "1:40"


def test_fmt_goal_range_fixed_and_max_only() -> None:
    assert _fmt_goal(20, 22) == "20-22s"
    assert _fmt_goal(15, None) == "15s"
    assert _fmt_goal(None, 22) == "≤22s"
    assert _fmt_goal(None, None) == "—"


def test_fmt_target_renders_range_and_meters() -> None:
    item = {
        "target_reps": 1,
        "target_duration_seconds": 20,
        "target_duration_max_seconds": 22,
        "target_distance_m": 400,
    }
    assert _fmt_target(item) == "1 reps · 20-22s · 400m"


def test_fmt_distance_yd_native_vs_track() -> None:
    assert _fmt_distance(36.576) == "40yd"  # 40yd dash stored in meters
    assert _fmt_distance(200) == "200m"
    assert _fmt_distance(804) == "804m"


def test_goal_status() -> None:
    assert _goal_status(21, 20, 22) == "[green]hit[/green]"
    assert _goal_status(19, 20, 22) == "[green]fast[/green]"
    assert _goal_status(23, 20, 22) == "[red]missed[/red]"
    assert _goal_status(15, 15, None) == "[green]hit[/green]"  # fixed goal, exact
    assert _goal_status(16, 15, None) == "[green]hit[/green]"  # +1s grace
    assert _goal_status(100, 20, 22) == "[red]missed[/red]"  # the stop-and-walk segment
    assert _goal_status(14, None, None) == ""  # no goal, no verdict
