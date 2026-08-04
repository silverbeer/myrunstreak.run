-- =====================================================
-- Project completed workouts → metric_entries (SB-509)
-- =====================================================
-- "Complete 12 workouts in August" needs no new goal kind: `frequency`, `month`
-- and the `count` aggregation all already exist. What was missing is anything to
-- count — metric_types seeded only running_distance, body_weight and pushups
-- (20260602120000), and workout_sessions landed a fortnight later
-- (20260620000000) without the projection runs got in 20260603120000.
--
-- This adds the missing half: a `workout_session` metric, and a trigger that
-- mirrors each COMPLETED session into metric_entries as value 1.
--
--   one metric_entry per completed session
--   source      = 'workout'
--   external_id = workout_sessions.id (dedup key — partial-unique index)
--   value       = 1   (metric_entries.value is documented as "1 for a session")
--   occurred_on = workout_sessions.session_date
--
-- Two goal shapes fall out of the one metric row, and they differ:
--
--   volume    + count aggregation  → counts SESSIONS  (a two-a-day counts 2)
--   frequency                      → counts DISTINCT DAYS (a two-a-day counts 1)
--
-- Both are selectable in the goal form; see backend/metrics_progress.py.
--
-- occurred_at is deliberately left NULL: a session records a date, not a start
-- time, so it cannot honour a `before_time` goal and must not pretend to.
--
-- =====================================================
-- WHAT COUNTS AS COMPLETED
-- =====================================================
-- A session row with at least one exercise_set. A session with no sets is an
-- empty shell — scheduled, abandoned, or half-created by the logger — and must
-- not tick a goal. That makes exercise_sets part of the trigger surface: the
-- first set completes a session, deleting the last one un-completes it.
--
-- =====================================================
-- WHOSE GOAL IT COUNTS TOWARD
-- =====================================================
-- workout_sessions.user_id is the ACTOR, not the subject. A coach logging for an
-- athlete writes user_id = the coach and athlete_id = the athlete (see
-- _owner_fields in src/shared/supabase_ops/workout_repository.py). Projecting on
-- user_id would credit the coach's own goals with their athlete's work.
--
-- So the subject is:
--   athlete_id IS NULL  → user_id             (a self-logged workout)
--   athlete_id set      → athletes.linked_user_id
--
-- A managed athlete with no login has linked_user_id NULL — there is no user to
-- credit, so nothing projects. If that athlete links later, the trigger on
-- athletes below backfills their history rather than leaving the goal at zero.

-- =====================================================
-- The metric
-- =====================================================
INSERT INTO metric_types (key, display_name, unit, aggregation, higher_is_better) VALUES
    ('workout_session', 'Workouts', 'session', 'count', TRUE)
ON CONFLICT (key) DO NOTHING;

-- =====================================================
-- Subject resolution
-- =====================================================
CREATE OR REPLACE FUNCTION workout_metric_subject(p_user_id UUID, p_athlete_id UUID)
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT CASE
        WHEN p_athlete_id IS NULL THEN p_user_id
        ELSE (SELECT linked_user_id FROM athletes WHERE id = p_athlete_id)
    END;
$$;

COMMENT ON FUNCTION workout_metric_subject IS
    'Whose goals a workout counts toward: the linked athlete, else the logging user (SB-509)';

-- =====================================================
-- Sync one session's metric entry
-- =====================================================
-- Recompute-from-scratch rather than incremental: every trigger below calls this
-- with a session id and it decides whether an entry should exist. That makes
-- insert, edit, un-completion and deletion the same code path, and makes the
-- whole thing idempotent.
--
-- SECURITY DEFINER because metric_entries RLS is strict (user_id = auth.uid())
-- with no anon escape. A coach logging sets through the anon key would otherwise
-- have the trigger's insert of the ATHLETE's entry rejected, failing their write.
-- The backend's service-role key is RLS-exempt and unaffected either way.
CREATE OR REPLACE FUNCTION sync_workout_session_metric_entry(p_session_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    s        workout_sessions%ROWTYPE;
    subject  UUID;
    has_sets BOOLEAN := FALSE;
    exists_  BOOLEAN;
BEGIN
    SELECT * INTO s FROM workout_sessions WHERE id = p_session_id;
    -- Capture FOUND immediately: the next SELECT INTO would overwrite it.
    exists_ := FOUND;

    IF exists_ THEN
        subject := workout_metric_subject(s.user_id, s.athlete_id);
        SELECT EXISTS (SELECT 1 FROM exercise_sets WHERE session_id = p_session_id)
          INTO has_sets;
    END IF;

    -- Gone, empty, or unattributable → no entry should exist.
    IF NOT exists_ OR subject IS NULL OR NOT has_sets THEN
        DELETE FROM metric_entries
         WHERE metric_key = 'workout_session'
           AND source = 'workout'
           AND external_id = p_session_id::TEXT;
        RETURN;
    END IF;

    -- The subject can change (an athlete links a login, or a session is
    -- reassigned), so drop any entry now credited to the wrong user.
    DELETE FROM metric_entries
     WHERE metric_key = 'workout_session'
       AND source = 'workout'
       AND external_id = p_session_id::TEXT
       AND user_id <> subject;

    INSERT INTO metric_entries (
        user_id, metric_key, occurred_on, value, source, external_id
    )
    VALUES (
        subject, 'workout_session', s.session_date, 1, 'workout', p_session_id::TEXT
    )
    ON CONFLICT (user_id, metric_key, source, external_id) WHERE external_id IS NOT NULL
    DO UPDATE SET
        occurred_on = EXCLUDED.occurred_on,
        updated_at = NOW();
END;
$$;

COMMENT ON FUNCTION sync_workout_session_metric_entry IS
    'Recomputes the metric_entries row for one workout session (SB-509)';

-- =====================================================
-- Triggers
-- =====================================================

-- The session itself: created, its date or owner edited, or deleted.
CREATE OR REPLACE FUNCTION trg_workout_session_metric_entry()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM sync_workout_session_metric_entry(OLD.id);
        RETURN OLD;
    END IF;
    PERFORM sync_workout_session_metric_entry(NEW.id);
    RETURN NEW;
END;
$$;

CREATE TRIGGER workout_session_metric_entry_trigger
    AFTER INSERT OR UPDATE OR DELETE ON workout_sessions
    FOR EACH ROW EXECUTE FUNCTION trg_workout_session_metric_entry();

-- The sets: the first one completes a session, the last one removed un-completes
-- it. An UPDATE that moves a set between sessions has to resync both.
CREATE OR REPLACE FUNCTION trg_exercise_set_metric_entry()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        PERFORM sync_workout_session_metric_entry(NEW.session_id);
    ELSIF TG_OP = 'DELETE' THEN
        PERFORM sync_workout_session_metric_entry(OLD.session_id);
    ELSE  -- UPDATE OF session_id: both sides may change completeness
        PERFORM sync_workout_session_metric_entry(OLD.session_id);
        IF NEW.session_id IS DISTINCT FROM OLD.session_id THEN
            PERFORM sync_workout_session_metric_entry(NEW.session_id);
        END IF;
    END IF;
    RETURN NULL;  -- AFTER trigger; return value is ignored
END;
$$;

CREATE TRIGGER exercise_set_metric_entry_trigger
    AFTER INSERT OR UPDATE OF session_id OR DELETE ON exercise_sets
    FOR EACH ROW EXECUTE FUNCTION trg_exercise_set_metric_entry();

-- Linking an athlete to a login makes their whole history attributable at once.
CREATE OR REPLACE FUNCTION trg_athlete_link_metric_entries()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    sid UUID;
BEGIN
    FOR sid IN SELECT id FROM workout_sessions WHERE athlete_id = NEW.id LOOP
        PERFORM sync_workout_session_metric_entry(sid);
    END LOOP;
    RETURN NULL;
END;
$$;

CREATE TRIGGER athlete_link_metric_entries_trigger
    AFTER UPDATE OF linked_user_id ON athletes
    FOR EACH ROW
    WHEN (NEW.linked_user_id IS DISTINCT FROM OLD.linked_user_id)
    EXECUTE FUNCTION trg_athlete_link_metric_entries();

-- =====================================================
-- Backfill
-- =====================================================
-- A monthly goal that only counts from the day the feature shipped is a broken
-- monthly goal: progress is computed over the goal's window, so August workouts
-- logged before this migration have to be there. Idempotent via the same
-- conflict target as the trigger.
INSERT INTO metric_entries (
    user_id, metric_key, occurred_on, value, source, external_id
)
SELECT
    subj.uid,
    'workout_session',
    s.session_date,
    1,
    'workout',
    s.id::TEXT
FROM workout_sessions s
CROSS JOIN LATERAL (
    SELECT workout_metric_subject(s.user_id, s.athlete_id) AS uid
) subj
WHERE subj.uid IS NOT NULL
  AND EXISTS (SELECT 1 FROM exercise_sets es WHERE es.session_id = s.id)
ON CONFLICT (user_id, metric_key, source, external_id) WHERE external_id IS NOT NULL
DO UPDATE SET
    occurred_on = EXCLUDED.occurred_on,
    updated_at = NOW();
