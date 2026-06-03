-- =====================================================
-- Project runs → metric_entries (running becomes "metric #1")
-- =====================================================
-- The generic metric engine reads from metric_entries. Runs live in their own
-- table, so running goals/streaks had no data. This makes every run flow into
-- the engine as a `running_distance` entry:
--
--   one metric_entry per run
--   source      = 'run'                  (provenance: run-derived, not manual)
--   external_id = runs.source_activity_id (dedup key — partial-unique index)
--   value       = runs.distance_km
--   occurred_on = runs.start_date
--
-- A trigger keeps entries in sync on insert/update/delete; a one-time backfill
-- covers existing runs. No application code changes.
--
-- The backend writes runs with the service-role key (bypasses RLS), so the
-- trigger's insert into metric_entries is unaffected by the strict RLS on that
-- table. metric_entries keeps multiple-per-day entries (several runs in a day
-- each project separately and sum under the 'sum' aggregation).
-- =====================================================

CREATE OR REPLACE FUNCTION project_run_to_metric_entry()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        DELETE FROM metric_entries
         WHERE user_id = OLD.user_id
           AND metric_key = 'running_distance'
           AND source = 'run'
           AND external_id = OLD.source_activity_id;
        RETURN OLD;
    END IF;

    INSERT INTO metric_entries (
        user_id, metric_key, occurred_on, occurred_at, value, source, external_id
    )
    VALUES (
        NEW.user_id,
        'running_distance',
        NEW.start_date,
        NEW.start_date_time_local,
        NEW.distance_km,
        'run',
        NEW.source_activity_id
    )
    ON CONFLICT (user_id, metric_key, source, external_id) WHERE external_id IS NOT NULL
    DO UPDATE SET
        value = EXCLUDED.value,
        occurred_on = EXCLUDED.occurred_on,
        occurred_at = EXCLUDED.occurred_at,
        updated_at = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER project_run_to_metric_entry_trigger
    AFTER INSERT OR UPDATE OR DELETE ON runs
    FOR EACH ROW EXECUTE FUNCTION project_run_to_metric_entry();

COMMENT ON FUNCTION project_run_to_metric_entry IS
    'Mirrors each run into metric_entries as a running_distance entry (source=run)';

-- One-time backfill of existing runs. Idempotent via the same conflict target,
-- so re-running the migration (or applying after some runs already projected)
-- is safe.
INSERT INTO metric_entries (
    user_id, metric_key, occurred_on, occurred_at, value, source, external_id
)
SELECT
    user_id,
    'running_distance',
    start_date,
    start_date_time_local,
    distance_km,
    'run',
    source_activity_id
FROM runs
ON CONFLICT (user_id, metric_key, source, external_id) WHERE external_id IS NOT NULL
DO UPDATE SET
    value = EXCLUDED.value,
    occurred_on = EXCLUDED.occurred_on,
    occurred_at = EXCLUDED.occurred_at,
    updated_at = NOW();
