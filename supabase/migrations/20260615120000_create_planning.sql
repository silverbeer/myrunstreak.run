-- =====================================================
-- Adaptive Monthly Planning — constraints + prescriptions + readiness (SB-163)
-- =====================================================
-- Turns monthly metric_goals into a day-by-day plan that adapts to reality.
-- Three additive tables; metric_types / metric_entries / metric_goals are
-- untouched. The plan is a DERIVED CACHE — always recomputable from
-- metric_goals + metric_entries + plan_constraints + readiness_log. See the
-- engine in src/shared/planning/.
--
--   plan_constraints  known-in-advance limits (travel cap, injury window)
--   plan_days         generated prescriptions, keyed by (metric, day)
--   readiness_log     daily "how I feel" signal
--
-- A prescription is per (metric_key, plan_on), NOT per goal: one run satisfies
-- every running goal at once (streak floor + long runs + volume), so the engine
-- collapses them into a single daily prescription via precedence.
--
-- RLS: all three are STRICT (user_id = auth.uid()), NO anon escape — planning
-- data is personal (matches metric_entries / metric_goals).
-- =====================================================

-- ===== Enums =====
CREATE TYPE plan_day_kind AS ENUM ('long', 'easy', 'rest', 'fixed');
CREATE TYPE readiness_status AS ENUM ('good', 'tired', 'sick');

-- =====================================================
-- plan_constraints — known-in-advance limits on a metric over a date range
-- =====================================================
CREATE TABLE plan_constraints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    metric_key TEXT NOT NULL REFERENCES metric_types(key),

    start_on DATE NOT NULL,
    end_on DATE NOT NULL,
    cap NUMERIC(12, 3),                          -- max prescribable value/day (canonical units)
    floor NUMERIC(12, 3),                        -- min still required/day
    reason TEXT CHECK (reason IS NULL OR LENGTH(reason) <= 200),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT plan_constraints_range CHECK (end_on >= start_on),
    CONSTRAINT plan_constraints_floor_le_cap
        CHECK (cap IS NULL OR floor IS NULL OR floor <= cap)
);

CREATE INDEX idx_plan_constraints_user_metric_range
    ON plan_constraints (user_id, metric_key, start_on, end_on);

COMMENT ON TABLE plan_constraints IS 'Known-in-advance limits (travel cap, injury window) the planner pins; canonical units (km for distance)';
COMMENT ON COLUMN plan_constraints.cap IS 'Max prescribable value/day; with floor=cap the day is pinned (e.g. Chicago = 1 mi)';

-- =====================================================
-- plan_days — generated prescriptions (the derived cache)
-- =====================================================
-- One row per (user, metric, day). Rebuilt every recompute (delete-future +
-- reinsert); past rows are preserved as the record of what was asked.
CREATE TABLE plan_days (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    metric_key TEXT NOT NULL REFERENCES metric_types(key),

    plan_on DATE NOT NULL,
    prescribed_value NUMERIC(12, 3) NOT NULL CHECK (prescribed_value >= 0),
    kind plan_day_kind NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT NOW(),      -- which recompute produced this row

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- One prescription per metric per day; a recompute upserts on this key.
    CONSTRAINT plan_days_unique UNIQUE (user_id, metric_key, plan_on)
);

CREATE INDEX idx_plan_days_user_metric_date
    ON plan_days (user_id, metric_key, plan_on);

COMMENT ON TABLE plan_days IS 'Generated daily prescriptions; a derived cache, recomputed nightly from goals + entries + constraints + readiness';
COMMENT ON COLUMN plan_days.kind IS 'long | easy | rest | fixed (constraint-locked)';

-- =====================================================
-- readiness_log — daily "how I feel" signal
-- =====================================================
CREATE TABLE readiness_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    log_on DATE NOT NULL,
    status readiness_status NOT NULL DEFAULT 'good',
    note TEXT CHECK (note IS NULL OR LENGTH(note) <= 400),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- One readiness signal per day; a new post updates it.
    CONSTRAINT readiness_log_unique UNIQUE (user_id, log_on)
);

CREATE INDEX idx_readiness_log_user_date ON readiness_log (user_id, log_on DESC);

COMMENT ON TABLE readiness_log IS 'Daily how-I-feel signal; tired down-shifts the day, sick rests it (streak floor preserved)';

-- =====================================================
-- Triggers — maintain updated_at (function from initial_schema)
-- =====================================================
CREATE TRIGGER update_plan_constraints_updated_at BEFORE UPDATE ON plan_constraints
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_plan_days_updated_at BEFORE UPDATE ON plan_days
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_readiness_log_updated_at BEFORE UPDATE ON readiness_log
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- Row Level Security — STRICT per-user, no anon escape
-- =====================================================
ALTER TABLE plan_constraints ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_days ENABLE ROW LEVEL SECURITY;
ALTER TABLE readiness_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users select their own plan_constraints"
    ON plan_constraints FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users insert their own plan_constraints"
    ON plan_constraints FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Users update their own plan_constraints"
    ON plan_constraints FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY "Users delete their own plan_constraints"
    ON plan_constraints FOR DELETE USING (user_id = auth.uid());

CREATE POLICY "Users select their own plan_days"
    ON plan_days FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users insert their own plan_days"
    ON plan_days FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Users update their own plan_days"
    ON plan_days FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY "Users delete their own plan_days"
    ON plan_days FOR DELETE USING (user_id = auth.uid());

CREATE POLICY "Users select their own readiness_log"
    ON readiness_log FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users insert their own readiness_log"
    ON readiness_log FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Users update their own readiness_log"
    ON readiness_log FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY "Users delete their own readiness_log"
    ON readiness_log FOR DELETE USING (user_id = auth.uid());
