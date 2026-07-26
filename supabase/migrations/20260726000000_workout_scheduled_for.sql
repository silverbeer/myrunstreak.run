-- =====================================================
-- Scheduled date for a workout template (SB-335)
-- =====================================================
-- An optional date a coach-assigned workout is scheduled for. Distinct from
-- created_at (when it was built) and from completion (a logged session). The
-- template name ("Monday At-Home") carried no real date before this. Nullable;
-- existing rows are unaffected and inherit the table's RLS policies.

ALTER TABLE workout_templates ADD COLUMN IF NOT EXISTS scheduled_for DATE;
COMMENT ON COLUMN workout_templates.scheduled_for IS 'Optional date the workout is scheduled for (SB-335)';
