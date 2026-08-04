-- =====================================================
-- SB-509 — workout → metric_entries projection, verified against a real database
-- =====================================================
-- The projection is triggers and SQL, so the backend's fake-Supabase unit tests
-- cannot reach it. This exercises it against local Postgres and rolls back, so
-- it leaves no rows behind and is safe to re-run.
--
--   psql "$(supabase status -o env | grep ^DB_URL | cut -d= -f2- | tr -d '"')" \
--        -v ON_ERROR_STOP=1 -f supabase/tests/sb509_workout_metric_projection.sql
--
-- Prints "SB-509 projection: all assertions passed" on success; any failed
-- ASSERT aborts with the message naming the case.

BEGIN;

DO $$
DECLARE
    runner_id   UUID := gen_random_uuid();
    coach_id    UUID := gen_random_uuid();
    athlete_uid UUID := gen_random_uuid();
    linked_ath  UUID;
    managed_ath UUID;
    self_sess   UUID;
    ath_sess    UUID;
    mgd_sess    UUID;
    dup_sess    UUID;
    set_id      UUID;
    ex_key      TEXT;
    d           DATE := DATE '2026-08-05';
    n           INT;
    owner       UUID;
    got_date    DATE;
BEGIN
    SELECT key INTO ex_key FROM exercises LIMIT 1;
    ASSERT ex_key IS NOT NULL, 'fixture: exercise catalog is empty';

    INSERT INTO users (user_id, email) VALUES
        (runner_id,   'sb509-runner@test.local'),
        (coach_id,    'sb509-coach@test.local'),
        (athlete_uid, 'sb509-athlete@test.local');

    INSERT INTO athletes (display_name, linked_user_id, created_by)
        VALUES ('SB509 Linked', athlete_uid, coach_id) RETURNING id INTO linked_ath;
    INSERT INTO athletes (display_name, linked_user_id, created_by)
        VALUES ('SB509 Managed', NULL, coach_id) RETURNING id INTO managed_ath;

    -- ---------------------------------------------------------------
    -- 1. An empty session is not a completed workout
    -- ---------------------------------------------------------------
    INSERT INTO workout_sessions (user_id, session_date)
        VALUES (runner_id, d) RETURNING id INTO self_sess;

    SELECT COUNT(*) INTO n FROM metric_entries
     WHERE user_id = runner_id AND metric_key = 'workout_session';
    ASSERT n = 0, format('empty session projected an entry (got %s)', n);

    -- ---------------------------------------------------------------
    -- 2. The first set completes it
    -- ---------------------------------------------------------------
    INSERT INTO exercise_sets (user_id, session_id, exercise_key, reps)
        VALUES (runner_id, self_sess, ex_key, 10) RETURNING id INTO set_id;

    SELECT COUNT(*) INTO n FROM metric_entries
     WHERE user_id = runner_id AND metric_key = 'workout_session';
    ASSERT n = 1, format('first set did not project exactly one entry (got %s)', n);

    SELECT value, occurred_on INTO n, got_date FROM metric_entries
     WHERE metric_key = 'workout_session' AND external_id = self_sess::TEXT;
    ASSERT n = 1, format('entry value should be 1, got %s', n);
    ASSERT got_date = d, format('occurred_on should be the session date, got %s', got_date);

    -- A second set on the same session must not double-count.
    INSERT INTO exercise_sets (user_id, session_id, exercise_key, reps)
        VALUES (runner_id, self_sess, ex_key, 12);
    SELECT COUNT(*) INTO n FROM metric_entries
     WHERE user_id = runner_id AND metric_key = 'workout_session';
    ASSERT n = 1, format('a second set double-counted the session (got %s)', n);

    -- ---------------------------------------------------------------
    -- 3. Editing the session date moves the entry
    -- ---------------------------------------------------------------
    UPDATE workout_sessions SET session_date = d + 1 WHERE id = self_sess;
    SELECT occurred_on INTO got_date FROM metric_entries
     WHERE metric_key = 'workout_session' AND external_id = self_sess::TEXT;
    ASSERT got_date = d + 1, format('occurred_on did not follow the session date, got %s', got_date);

    -- ---------------------------------------------------------------
    -- 4. Two sessions on one day are two entries (volume+count = 2,
    --    frequency = 1 day — see backend/metrics_progress.py)
    -- ---------------------------------------------------------------
    INSERT INTO workout_sessions (user_id, session_date)
        VALUES (runner_id, d + 1) RETURNING id INTO dup_sess;
    INSERT INTO exercise_sets (user_id, session_id, exercise_key, reps)
        VALUES (runner_id, dup_sess, ex_key, 8);

    SELECT COUNT(*) INTO n FROM metric_entries
     WHERE user_id = runner_id AND metric_key = 'workout_session';
    ASSERT n = 2, format('two-a-day should be two entries (got %s)', n);
    SELECT COUNT(DISTINCT occurred_on) INTO n FROM metric_entries
     WHERE user_id = runner_id AND metric_key = 'workout_session';
    ASSERT n = 1, format('two-a-day should be one distinct day (got %s)', n);

    DELETE FROM workout_sessions WHERE id = dup_sess;

    -- ---------------------------------------------------------------
    -- 5. A coach logging for a linked athlete credits the ATHLETE
    -- ---------------------------------------------------------------
    INSERT INTO workout_sessions (user_id, athlete_id, created_by, session_date)
        VALUES (coach_id, linked_ath, coach_id, d) RETURNING id INTO ath_sess;
    INSERT INTO exercise_sets (user_id, athlete_id, session_id, exercise_key, reps)
        VALUES (coach_id, linked_ath, ath_sess, ex_key, 10);

    SELECT user_id INTO owner FROM metric_entries
     WHERE metric_key = 'workout_session' AND external_id = ath_sess::TEXT;
    ASSERT owner = athlete_uid,
        format('athlete session credited to %s, expected the athlete %s', owner, athlete_uid);

    SELECT COUNT(*) INTO n FROM metric_entries
     WHERE user_id = coach_id AND metric_key = 'workout_session';
    ASSERT n = 0, format('coach absorbed %s of their athlete''s workouts', n);

    -- ---------------------------------------------------------------
    -- 6. A managed athlete has nobody to credit — until they link
    -- ---------------------------------------------------------------
    INSERT INTO workout_sessions (user_id, athlete_id, created_by, session_date)
        VALUES (coach_id, managed_ath, coach_id, d) RETURNING id INTO mgd_sess;
    INSERT INTO exercise_sets (user_id, athlete_id, session_id, exercise_key, reps)
        VALUES (coach_id, managed_ath, mgd_sess, ex_key, 10);

    SELECT COUNT(*) INTO n FROM metric_entries
     WHERE metric_key = 'workout_session' AND external_id = mgd_sess::TEXT;
    ASSERT n = 0, format('unlinked athlete projected %s entries', n);

    UPDATE athletes SET linked_user_id = runner_id WHERE id = managed_ath;
    SELECT COUNT(*) INTO n FROM metric_entries
     WHERE user_id = runner_id AND metric_key = 'workout_session'
       AND external_id = mgd_sess::TEXT;
    ASSERT n = 1, format('linking an athlete did not backfill their history (got %s)', n);

    -- Re-linking to someone else must not leave the old credit behind.
    UPDATE athletes SET linked_user_id = athlete_uid WHERE id = managed_ath;
    SELECT COUNT(*) INTO n FROM metric_entries
     WHERE user_id = runner_id AND external_id = mgd_sess::TEXT;
    ASSERT n = 0, format('re-linking left %s stale entries on the old user', n);

    -- ---------------------------------------------------------------
    -- 7. Removing the last set un-completes the session
    -- ---------------------------------------------------------------
    DELETE FROM exercise_sets WHERE session_id = self_sess AND id <> set_id;
    SELECT COUNT(*) INTO n FROM metric_entries
     WHERE metric_key = 'workout_session' AND external_id = self_sess::TEXT;
    ASSERT n = 1, format('removing one of two sets dropped the entry (got %s)', n);

    DELETE FROM exercise_sets WHERE id = set_id;
    SELECT COUNT(*) INTO n FROM metric_entries
     WHERE metric_key = 'workout_session' AND external_id = self_sess::TEXT;
    ASSERT n = 0, format('removing the last set left %s entries', n);

    -- ---------------------------------------------------------------
    -- 8. Deleting the session removes its entry (cascade included)
    -- ---------------------------------------------------------------
    DELETE FROM workout_sessions WHERE id = ath_sess;
    SELECT COUNT(*) INTO n FROM metric_entries
     WHERE metric_key = 'workout_session' AND external_id = ath_sess::TEXT;
    ASSERT n = 0, format('deleting a session left %s entries', n);

    -- ---------------------------------------------------------------
    -- 9. The backfill is idempotent — re-running it changes no counts
    -- ---------------------------------------------------------------
    INSERT INTO workout_sessions (user_id, session_date)
        VALUES (runner_id, d) RETURNING id INTO self_sess;
    INSERT INTO exercise_sets (user_id, session_id, exercise_key, reps)
        VALUES (runner_id, self_sess, ex_key, 5);

    SELECT COUNT(*) INTO n FROM metric_entries WHERE metric_key = 'workout_session';

    INSERT INTO metric_entries (user_id, metric_key, occurred_on, value, source, external_id)
    SELECT subj.uid, 'workout_session', s.session_date, 1, 'workout', s.id::TEXT
      FROM workout_sessions s
      CROSS JOIN LATERAL (SELECT workout_metric_subject(s.user_id, s.athlete_id) AS uid) subj
     WHERE subj.uid IS NOT NULL
       AND EXISTS (SELECT 1 FROM exercise_sets es WHERE es.session_id = s.id)
    ON CONFLICT (user_id, metric_key, source, external_id) WHERE external_id IS NOT NULL
    DO UPDATE SET occurred_on = EXCLUDED.occurred_on, updated_at = NOW();

    ASSERT (SELECT COUNT(*) FROM metric_entries WHERE metric_key = 'workout_session') = n,
        'backfill is not idempotent — re-running it changed the entry count';

    RAISE NOTICE 'SB-509 projection: all assertions passed';
END $$;

ROLLBACK;
