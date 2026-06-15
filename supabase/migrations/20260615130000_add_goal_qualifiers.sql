-- =====================================================
-- metric_goals qualifiers — per-day threshold + per-event minimum (SB-164)
-- =====================================================
-- Additive columns the planning engine needs to map a stored goal to a
-- PlanningGoal (see src/shared/planning/). Both nullable — existing goals keep
-- today's behavior (any entry counts).
--
--   qualifier_threshold  a day must reach this aggregate to "count":
--                          streak    → daily floor (run >= 1 mi/day)
--                          frequency → per-day threshold (a run >= 5 mi is one
--                                      of the "4 long runs")
--   per_event_min        minimum value each qualifying event needs
--                          (push-ups >= 60 per session)
--
-- This is the additive "qualified goals" step from docs/GOALS_TRACKING.md, scoped
-- to exactly what planning requires. Canonical units (km for distance, reps, ...).
-- =====================================================

ALTER TABLE metric_goals
    ADD COLUMN qualifier_threshold NUMERIC(12, 3) CHECK (qualifier_threshold IS NULL OR qualifier_threshold >= 0),
    ADD COLUMN per_event_min NUMERIC(12, 3) CHECK (per_event_min IS NULL OR per_event_min >= 0);

COMMENT ON COLUMN metric_goals.qualifier_threshold IS 'Per-day aggregate a day must reach to count (streak floor / frequency threshold); canonical units';
COMMENT ON COLUMN metric_goals.per_event_min IS 'Minimum value each qualifying event needs (e.g. push-ups >= 60 per session)';
