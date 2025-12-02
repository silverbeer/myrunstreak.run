-- Migration: Add user_running_stats aggregation table
-- This table stores pre-calculated running statistics to avoid row limit issues
-- when querying large datasets (e.g., 11+ year running streaks)

-- =====================================================
-- AGGREGATION TABLE
-- =====================================================

CREATE TABLE user_running_stats (
    user_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,

    -- Lifetime totals
    lifetime_runs INTEGER NOT NULL DEFAULT 0,
    lifetime_distance_km NUMERIC(10,2) NOT NULL DEFAULT 0,
    lifetime_duration_seconds BIGINT NOT NULL DEFAULT 0,

    -- Current streak
    current_streak_days INTEGER NOT NULL DEFAULT 0,
    current_streak_start DATE,
    current_streak_distance_km NUMERIC(10,2) NOT NULL DEFAULT 0,

    -- Longest streak (for records)
    longest_streak_days INTEGER NOT NULL DEFAULT 0,
    longest_streak_start DATE,
    longest_streak_end DATE,

    -- Period totals (reset daily by recalculation)
    year_to_date_distance_km NUMERIC(10,2) NOT NULL DEFAULT 0,
    year_to_date_runs INTEGER NOT NULL DEFAULT 0,
    month_to_date_distance_km NUMERIC(10,2) NOT NULL DEFAULT 0,
    month_to_date_runs INTEGER NOT NULL DEFAULT 0,

    -- Metadata
    last_run_date DATE,
    last_calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE user_running_stats ENABLE ROW LEVEL SECURITY;

-- RLS policies
CREATE POLICY "Users can view own stats"
    ON user_running_stats FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Service role has full access to stats"
    ON user_running_stats FOR ALL
    USING (auth.role() = 'service_role');

COMMENT ON TABLE user_running_stats IS 'Pre-calculated running statistics per user. Updated after each sync.';

-- =====================================================
-- RECALCULATION FUNCTION
-- =====================================================

CREATE OR REPLACE FUNCTION recalculate_user_stats(p_user_id UUID)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_lifetime_runs INTEGER;
    v_lifetime_distance_km NUMERIC(10,2);
    v_lifetime_duration_seconds BIGINT;
    v_current_streak_days INTEGER;
    v_current_streak_start DATE;
    v_current_streak_distance_km NUMERIC(10,2);
    v_longest_streak_days INTEGER;
    v_longest_streak_start DATE;
    v_longest_streak_end DATE;
    v_ytd_distance_km NUMERIC(10,2);
    v_ytd_runs INTEGER;
    v_mtd_distance_km NUMERIC(10,2);
    v_mtd_runs INTEGER;
    v_last_run_date DATE;
    v_today DATE := CURRENT_DATE;
    v_year_start DATE := DATE_TRUNC('year', CURRENT_DATE)::DATE;
    v_month_start DATE := DATE_TRUNC('month', CURRENT_DATE)::DATE;
    v_streak_stats JSON;
BEGIN
    -- Calculate lifetime totals
    SELECT
        COUNT(*)::INTEGER,
        COALESCE(SUM(distance_km), 0)::NUMERIC(10,2),
        COALESCE(SUM(duration_seconds), 0)::BIGINT,
        MAX(start_date)
    INTO
        v_lifetime_runs,
        v_lifetime_distance_km,
        v_lifetime_duration_seconds,
        v_last_run_date
    FROM runs
    WHERE user_id = p_user_id;

    -- Get current streak using existing function
    SELECT get_current_streak(p_user_id) INTO v_current_streak_days;

    -- Calculate streak start date
    IF v_current_streak_days > 0 THEN
        -- If ran today, streak started (streak_days - 1) days ago
        -- If not ran today but ran yesterday, streak started (streak_days) days ago from yesterday
        IF EXISTS (SELECT 1 FROM runs WHERE user_id = p_user_id AND start_date = v_today) THEN
            v_current_streak_start := v_today - (v_current_streak_days - 1);
        ELSE
            v_current_streak_start := (v_today - 1) - (v_current_streak_days - 1);
        END IF;

        -- Calculate total distance during current streak
        SELECT COALESCE(SUM(distance_km), 0)::NUMERIC(10,2)
        INTO v_current_streak_distance_km
        FROM runs
        WHERE user_id = p_user_id
          AND start_date >= v_current_streak_start
          AND start_date <= v_today;
    ELSE
        v_current_streak_start := NULL;
        v_current_streak_distance_km := 0;
    END IF;

    -- Get longest streak stats using existing function
    SELECT get_streak_stats(p_user_id) INTO v_streak_stats;
    v_longest_streak_days := (v_streak_stats->>'longest_streak')::INTEGER;
    v_longest_streak_start := (v_streak_stats->>'longest_start')::DATE;
    v_longest_streak_end := (v_streak_stats->>'longest_end')::DATE;

    -- Calculate year-to-date totals
    SELECT
        COALESCE(SUM(distance_km), 0)::NUMERIC(10,2),
        COUNT(*)::INTEGER
    INTO v_ytd_distance_km, v_ytd_runs
    FROM runs
    WHERE user_id = p_user_id
      AND start_date >= v_year_start
      AND start_date <= v_today;

    -- Calculate month-to-date totals
    SELECT
        COALESCE(SUM(distance_km), 0)::NUMERIC(10,2),
        COUNT(*)::INTEGER
    INTO v_mtd_distance_km, v_mtd_runs
    FROM runs
    WHERE user_id = p_user_id
      AND start_date >= v_month_start
      AND start_date <= v_today;

    -- Upsert the stats row
    INSERT INTO user_running_stats (
        user_id,
        lifetime_runs,
        lifetime_distance_km,
        lifetime_duration_seconds,
        current_streak_days,
        current_streak_start,
        current_streak_distance_km,
        longest_streak_days,
        longest_streak_start,
        longest_streak_end,
        year_to_date_distance_km,
        year_to_date_runs,
        month_to_date_distance_km,
        month_to_date_runs,
        last_run_date,
        last_calculated_at,
        updated_at
    ) VALUES (
        p_user_id,
        v_lifetime_runs,
        v_lifetime_distance_km,
        v_lifetime_duration_seconds,
        v_current_streak_days,
        v_current_streak_start,
        v_current_streak_distance_km,
        v_longest_streak_days,
        v_longest_streak_start,
        v_longest_streak_end,
        v_ytd_distance_km,
        v_ytd_runs,
        v_mtd_distance_km,
        v_mtd_runs,
        v_last_run_date,
        NOW(),
        NOW()
    )
    ON CONFLICT (user_id) DO UPDATE SET
        lifetime_runs = EXCLUDED.lifetime_runs,
        lifetime_distance_km = EXCLUDED.lifetime_distance_km,
        lifetime_duration_seconds = EXCLUDED.lifetime_duration_seconds,
        current_streak_days = EXCLUDED.current_streak_days,
        current_streak_start = EXCLUDED.current_streak_start,
        current_streak_distance_km = EXCLUDED.current_streak_distance_km,
        longest_streak_days = EXCLUDED.longest_streak_days,
        longest_streak_start = EXCLUDED.longest_streak_start,
        longest_streak_end = EXCLUDED.longest_streak_end,
        year_to_date_distance_km = EXCLUDED.year_to_date_distance_km,
        year_to_date_runs = EXCLUDED.year_to_date_runs,
        month_to_date_distance_km = EXCLUDED.month_to_date_distance_km,
        month_to_date_runs = EXCLUDED.month_to_date_runs,
        last_run_date = EXCLUDED.last_run_date,
        last_calculated_at = EXCLUDED.last_calculated_at,
        updated_at = EXCLUDED.updated_at;

    -- Return the calculated stats
    RETURN json_build_object(
        'user_id', p_user_id,
        'lifetime_runs', v_lifetime_runs,
        'lifetime_distance_km', v_lifetime_distance_km,
        'current_streak_days', v_current_streak_days,
        'current_streak_start', v_current_streak_start,
        'current_streak_distance_km', v_current_streak_distance_km,
        'longest_streak_days', v_longest_streak_days,
        'year_to_date_distance_km', v_ytd_distance_km,
        'month_to_date_distance_km', v_mtd_distance_km,
        'last_run_date', v_last_run_date,
        'calculated_at', NOW()
    );
END;
$$;

GRANT EXECUTE ON FUNCTION recalculate_user_stats(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION recalculate_user_stats(UUID) TO service_role;

COMMENT ON FUNCTION recalculate_user_stats IS 'Recalculates and stores all running statistics for a user. Call after syncing runs.';

-- =====================================================
-- INDEX FOR PERFORMANCE
-- =====================================================

CREATE INDEX idx_user_running_stats_updated
    ON user_running_stats(last_calculated_at DESC);
