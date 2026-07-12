-- =====================================================
-- Time of day (SB-270): precomputed start hour
-- =====================================================
-- Same pattern as start_year/month/day_of_week: a filterable integer for the
-- runner's local wall-clock start hour. Powers morning/evening filters, the
-- "Early bird" collection, and morning-vs-evening pace comparisons.
--
-- SmashRun's startDateTimeLocal carries a UTC offset, so the timestamptz
-- column holds the correct instant normalized to UTC; recover the wall time
-- via the runner's home zone. The per-run timezone column is empty across the
-- history, so America/New_York (the account's home zone) is assumed for the
-- backfill; the sync mapper computes start_hour from the offset-aware datetime
-- going forward.

ALTER TABLE runs ADD COLUMN IF NOT EXISTS start_hour SMALLINT;
UPDATE runs SET start_hour = date_part('hour', start_date_time_local AT TIME ZONE 'America/New_York');
CREATE INDEX IF NOT EXISTS idx_runs_start_hour ON runs (user_id, start_hour);
COMMENT ON COLUMN runs.start_hour IS 'Local wall-clock start hour 0-23 (SB-270)';
