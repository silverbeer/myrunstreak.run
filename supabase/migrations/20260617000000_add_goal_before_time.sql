-- =====================================================
-- metric_goals.before_time — "start the activity by this clock time" qualifier
-- =====================================================
-- Additive, nullable. Powers time-of-day habit goals like "start a run by 8am,
-- 3x per week" (frequency + period=week + before_time='08:00'). A day counts
-- toward the goal only if that day's entry started at/before this local time.
--
-- Evaluated against metric_entries.occurred_at (the activity's local start time,
-- projected from runs.start_date_time_local). Local tz = America/New_York, the
-- app-wide anchor. Tracked + coached via the goals/progress engine; it does not
-- change planning prescriptions. See docs/GOALS_TRACKING.md.
-- =====================================================

ALTER TABLE metric_goals
    ADD COLUMN before_time TIME;

COMMENT ON COLUMN metric_goals.before_time IS 'Time-of-day qualifier: a day counts only if its entry started at/before this local clock time (e.g. 08:00 = "out the door by 8am")';
