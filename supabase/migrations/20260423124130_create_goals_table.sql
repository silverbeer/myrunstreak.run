-- =====================================================
-- Goals - SmashRun yearly/monthly running goals
-- =====================================================
-- Stores yearly and monthly distance goals fetched from SmashRun.
-- Fetches are cached with a per-period staleness threshold to avoid
-- re-fetching the same goal every sync.
--
-- month IS NULL      -> yearly goal for (user, source, year)
-- month BETWEEN 1,12 -> monthly goal for (user, source, year, month)
-- =====================================================

CREATE TABLE goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign Keys
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES user_sources(id) ON DELETE CASCADE,

    -- Period
    year INTEGER NOT NULL CHECK (year >= 2000 AND year <= 2100),
    month INTEGER CHECK (month BETWEEN 1 AND 12),

    -- Goal data from SmashRun (distance stored in km for consistency with runs.distance_km)
    goal_text TEXT,
    goal_km NUMERIC(10, 3) CHECK (goal_km IS NULL OR goal_km > 0),
    progress_km NUMERIC(10, 3) CHECK (progress_km IS NULL OR progress_km >= 0),

    -- Cache control
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraints: one yearly row and one monthly row per (user, source, year[, month]).
-- Partial indexes are required because (user_id, source_id, year, month) with NULL month
-- would not enforce uniqueness on yearly rows (NULLs are not equal in PostgreSQL).
CREATE UNIQUE INDEX idx_goals_yearly_unique
    ON goals (user_id, source_id, year)
    WHERE month IS NULL;

CREATE UNIQUE INDEX idx_goals_monthly_unique
    ON goals (user_id, source_id, year, month)
    WHERE month IS NOT NULL;

-- Lookup index for common queries
CREATE INDEX idx_goals_user_period ON goals (user_id, year, month);

COMMENT ON TABLE goals IS 'Yearly and monthly running goals fetched from source APIs';
COMMENT ON COLUMN goals.month IS 'NULL = yearly goal, 1-12 = monthly goal';
COMMENT ON COLUMN goals.goal_km IS 'Target distance in kilometers (SmashRun native unit)';
COMMENT ON COLUMN goals.progress_km IS 'Progress toward goal in kilometers (snapshot at fetch time)';
COMMENT ON COLUMN goals.fetched_at IS 'Last time this goal was refreshed from the source API';

-- Enable Row Level Security
ALTER TABLE goals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own goals"
    ON goals FOR SELECT
    USING (user_id = auth.uid() OR auth.uid() IS NULL);

CREATE POLICY "Users can insert their own goals"
    ON goals FOR INSERT
    WITH CHECK (user_id = auth.uid() OR auth.uid() IS NULL);

CREATE POLICY "Users can update their own goals"
    ON goals FOR UPDATE
    USING (user_id = auth.uid() OR auth.uid() IS NULL);

-- Auto-update updated_at
CREATE TRIGGER update_goals_updated_at BEFORE UPDATE ON goals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
