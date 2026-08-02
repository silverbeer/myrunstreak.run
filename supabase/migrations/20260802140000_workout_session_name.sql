-- =====================================================
-- A logged session can be called something (SB-536)
-- =====================================================
-- SB-531 made it possible to log a workout with no plan behind it. Nothing
-- names those sessions, so SB-530's Completed list titles them on the session
-- *type* — "Circuit" — and four ad-hoc workouts in a week are indistinguishable
-- from one another. A session logged against a plan borrows the plan's name and
-- reads fine, so this is only felt on the path SB-531 opened.
--
-- Nullable, and deliberately not required by the API: asking for a name before
-- recording the work is friction in exactly the wrong place. The logger fills
-- in a default from the session's own date and lets it be changed — before
-- saving or long after.
--
-- Existing rows keep working: NULL falls back to the template name, then to the
-- type, which is what every row does today.

ALTER TABLE workout_sessions ADD COLUMN IF NOT EXISTS name TEXT;

COMMENT ON COLUMN workout_sessions.name IS
    'What the athlete calls this session; NULL falls back to the template name (SB-536)';
