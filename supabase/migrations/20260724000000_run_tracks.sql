-- =====================================================
-- Stored GPS polylines (SB-309): the north-star bridge
-- =====================================================
-- Persist each GPS run's track as a simplified, encoded polyline so route maps
-- stop re-fetching from SmashRun on every view, and so shape-based route
-- matching + the territory heatmap have data to work with.
--
-- Kept in its own table (not a column on runs) so the ~1-2 KB blob never bloats
-- the hot runs table that every list / leaderboard scans; loaded only when a
-- map or the heatmap needs it.

CREATE TABLE IF NOT EXISTS run_tracks (
    run_id UUID PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
    -- Google Encoded Polyline Algorithm Format, Douglas-Peucker simplified.
    polyline TEXT NOT NULL,
    point_count INTEGER NOT NULL,
    encoded_precision SMALLINT NOT NULL DEFAULT 5,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE run_tracks IS 'Simplified encoded GPS polyline per run (SB-309)';
COMMENT ON COLUMN run_tracks.polyline IS 'Google encoded polyline, Douglas-Peucker simplified';

ALTER TABLE run_tracks ENABLE ROW LEVEL SECURITY;

-- Owner-scoped: a track is visible/writable only to the user who owns its run.
-- Backend uses the service role (bypasses RLS); this guards any anon/auth path.
CREATE POLICY run_tracks_owner ON run_tracks
    USING (
        EXISTS (
            SELECT 1 FROM runs r
            WHERE r.id = run_tracks.run_id AND r.user_id = auth.uid()
        )
    );
