-- =====================================================
-- Run start location + GPS flag (SB-290, step 1 of SB-289)
-- =====================================================
-- SmashRun's /my/activities/search (list) payload already carries
-- startLatitude / startLongitude / hasDetailsGPS / isTreadmill — free on every
-- sync, no per-activity detail call. Capturing the start point unlocks the
-- near-free route-frequency MVP (group by rounded start cell + distance).
--
-- Backfill: none needed here. The sync mapper now emits these columns and
-- upsert_run overwrites on conflict, so `stk sync --full` repopulates every
-- existing run from the list endpoint (~48 pages, no detail calls).
--
-- Also fixes has_gps_data: it was derived from recordingKeys, which the list
-- endpoint never returns, so it was never set true by the search-based sync
-- (a bogus ~444/4774 in prod). The mapper now sources it from hasDetailsGPS.

ALTER TABLE runs ADD COLUMN IF NOT EXISTS start_latitude NUMERIC(9, 6);
ALTER TABLE runs ADD COLUMN IF NOT EXISTS start_longitude NUMERIC(9, 6);
ALTER TABLE runs ADD COLUMN IF NOT EXISTS is_treadmill BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN runs.start_latitude IS 'Run start latitude from SmashRun startLatitude (SB-290)';
COMMENT ON COLUMN runs.start_longitude IS 'Run start longitude from SmashRun startLongitude (SB-290)';
COMMENT ON COLUMN runs.is_treadmill IS 'Indoor/treadmill run from SmashRun isTreadmill (SB-290)';
