-- =====================================================
-- Generic Metric Tracking — types catalog + entries + goals
-- =====================================================
-- Running becomes "metric #1"; body weight, push-ups, weight training, and
-- future activities are just more rows in metric_types. Adding a trackable
-- activity is one catalog row, not a new schema.
--
--   metric_types   global catalog (running_distance, body_weight, pushups, ...)
--   metric_entries per-user unified log (synced runs OR manual logs)
--   metric_goals   per-user NATIVE goals (volume | frequency | streak)
--
-- The existing SmashRun-mirror `goals` table is intentionally untouched — it
-- stays the read-only cache of yearly/monthly running goals (see backend/goals.py).
-- Native, app-set goals live here. See docs/GOALS_TRACKING.md.
--
-- RLS: metric_entries / metric_goals are STRICT (user_id = auth.uid()) with NO
-- anon escape — body weight etc. are sensitive. The backend uses the service-role
-- key (bypasses RLS); these policies govern direct anon-key access (frontend
-- supabase-js with the user's JWT). metric_types is a public read-only catalog.
-- =====================================================

-- ===== Enums =====
CREATE TYPE metric_aggregation AS ENUM ('sum', 'count', 'latest', 'max');
CREATE TYPE metric_goal_kind AS ENUM ('volume', 'frequency', 'streak');
CREATE TYPE metric_goal_period AS ENUM ('year', 'month', 'week', 'custom');
CREATE TYPE metric_goal_comparator AS ENUM ('gte', 'lte');
CREATE TYPE metric_goal_status AS ENUM ('active', 'achieved', 'archived');

-- =====================================================
-- metric_types — global catalog of trackable metrics
-- =====================================================
CREATE TABLE metric_types (
    key TEXT PRIMARY KEY,                       -- stable slug: running_distance, body_weight, pushups
    display_name TEXT NOT NULL,
    unit TEXT NOT NULL,                         -- km, kg, reps, session
    aggregation metric_aggregation NOT NULL,    -- how entries roll up over a window
    higher_is_better BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE metric_types IS 'Global catalog of trackable metrics; running is just metric #1';
COMMENT ON COLUMN metric_types.aggregation IS 'sum | count | latest | max — how entries combine over a goal window';
COMMENT ON COLUMN metric_types.higher_is_better IS 'FALSE for loss goals (e.g. body weight)';

-- Seed the Phase 0 metrics (running foundational; weight + push-ups are the first
-- new trackers). More activities (lifts, planks, ...) are added as future rows.
INSERT INTO metric_types (key, display_name, unit, aggregation, higher_is_better) VALUES
    ('running_distance', 'Running distance', 'km', 'sum', TRUE),
    ('body_weight', 'Body weight', 'kg', 'latest', FALSE),
    ('pushups', 'Push-ups', 'reps', 'sum', TRUE);

-- =====================================================
-- metric_entries — per-user unified event log
-- =====================================================
-- Everything is an entry: a synced run, a logged set of push-ups, a weigh-in.
CREATE TABLE metric_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    metric_key TEXT NOT NULL REFERENCES metric_types(key),

    occurred_on DATE NOT NULL,                  -- the day this counts toward (local) — drives windows/streaks
    occurred_at TIMESTAMPTZ,                     -- precise time, optional

    value NUMERIC(12, 3) NOT NULL,               -- km, kg, reps, or 1 for a session/check-in
    note TEXT CHECK (note IS NULL OR LENGTH(note) <= 800),

    source TEXT NOT NULL DEFAULT 'manual',       -- manual | smashrun | strava | import | ...
    metadata JSONB,                              -- e.g. per-exercise breakdown for a lift
    external_id TEXT,                            -- dedup key for synced sources

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Primary lookup: a user's entries for a metric over time (streaks, windows, pace).
CREATE INDEX idx_metric_entries_user_metric_date
    ON metric_entries (user_id, metric_key, occurred_on DESC);

-- Dedup synced entries (many manual entries per day are allowed — e.g. several
-- push-up sets — but a synced source must not double-insert the same activity).
CREATE UNIQUE INDEX idx_metric_entries_external
    ON metric_entries (user_id, metric_key, source, external_id)
    WHERE external_id IS NOT NULL;

COMMENT ON TABLE metric_entries IS 'Per-user unified log of metric events (synced or manual)';
COMMENT ON COLUMN metric_entries.occurred_on IS 'Local day the entry counts toward; drives streaks and goal windows';
COMMENT ON COLUMN metric_entries.value IS 'Canonical unit per metric_types.unit (km, kg, reps); 1 for a session/check-in';

-- =====================================================
-- metric_goals — per-user NATIVE goals (not the SmashRun mirror)
-- =====================================================
CREATE TABLE metric_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    metric_key TEXT NOT NULL REFERENCES metric_types(key),

    kind metric_goal_kind NOT NULL,              -- volume | frequency | streak
    period metric_goal_period NOT NULL,          -- year | month | week | custom
    period_start DATE,                           -- required for 'custom'; derived otherwise
    period_end DATE,

    target NUMERIC(12, 3) NOT NULL CHECK (target > 0),
    comparator metric_goal_comparator NOT NULL DEFAULT 'gte',  -- gte = hit target, lte = stay under (weight)
    rest_budget INTEGER NOT NULL DEFAULT 0 CHECK (rest_budget >= 0),  -- allowed misses before a streak/frequency goal breaks

    status metric_goal_status NOT NULL DEFAULT 'active',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Custom periods must carry explicit bounds; named periods derive them.
    CONSTRAINT metric_goals_custom_bounds
        CHECK (period <> 'custom' OR (period_start IS NOT NULL AND period_end IS NOT NULL))
);

CREATE INDEX idx_metric_goals_user_status ON metric_goals (user_id, status);
CREATE INDEX idx_metric_goals_user_metric ON metric_goals (user_id, metric_key);

COMMENT ON TABLE metric_goals IS 'Per-user app-defined goals; progress computed from metric_entries';
COMMENT ON COLUMN metric_goals.kind IS 'volume = sum to target; frequency = count of qualifying days; streak = daily chain';
COMMENT ON COLUMN metric_goals.comparator IS 'gte = reach target; lte = stay under (e.g. body-weight goal)';
COMMENT ON COLUMN metric_goals.rest_budget IS 'Allowed misses per window before a streak/frequency goal is considered broken';

-- =====================================================
-- Triggers — maintain updated_at (function defined in initial_schema)
-- =====================================================
CREATE TRIGGER update_metric_types_updated_at BEFORE UPDATE ON metric_types
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_metric_entries_updated_at BEFORE UPDATE ON metric_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_metric_goals_updated_at BEFORE UPDATE ON metric_goals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- Row Level Security
-- =====================================================

-- metric_types: public read-only catalog. Writes via service role / migrations only.
ALTER TABLE metric_types ENABLE ROW LEVEL SECURITY;

CREATE POLICY "metric_types readable by all"
    ON metric_types FOR SELECT
    USING (TRUE);

-- metric_entries: STRICT per-user. No anon escape — sensitive personal data.
ALTER TABLE metric_entries ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users select their own metric_entries"
    ON metric_entries FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users insert their own metric_entries"
    ON metric_entries FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users update their own metric_entries"
    ON metric_entries FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users delete their own metric_entries"
    ON metric_entries FOR DELETE
    USING (user_id = auth.uid());

-- metric_goals: STRICT per-user. No anon escape.
ALTER TABLE metric_goals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users select their own metric_goals"
    ON metric_goals FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users insert their own metric_goals"
    ON metric_goals FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users update their own metric_goals"
    ON metric_goals FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users delete their own metric_goals"
    ON metric_goals FOR DELETE
    USING (user_id = auth.uid());
