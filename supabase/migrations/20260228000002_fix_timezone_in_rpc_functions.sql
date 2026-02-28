-- Migration: Fix UTC CURRENT_DATE in streak and stats RPC functions
--
-- Problem: get_current_streak and recalculate_user_stats use CURRENT_DATE which
-- is UTC in Supabase/PostgreSQL. But runs.start_date stores the user's LOCAL date
-- (Eastern time). At month/year boundaries or during manual triggers, UTC and
-- Eastern dates can differ, causing incorrect streak counts and period totals.
--
-- Fix: Accept a timezone parameter and use (NOW() AT TIME ZONE tz)::DATE instead
-- of CURRENT_DATE. Callers pass the user's timezone (e.g., 'America/New_York').
-- Default to 'America/New_York' for backward compatibility.
--
-- Related: GitHub Issue #32

-- =====================================================
-- FIX: get_current_streak - accept timezone parameter
-- =====================================================

-- Drop existing function first (signature change)
DROP FUNCTION IF EXISTS get_current_streak(UUID);

CREATE OR REPLACE FUNCTION get_current_streak(p_user_id UUID, p_timezone TEXT DEFAULT 'America/New_York')
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    streak_count INTEGER := 0;
    check_date DATE;
    has_run BOOLEAN;
BEGIN
    -- Use the user's local "today", not UTC
    check_date := (NOW() AT TIME ZONE p_timezone)::DATE;

    -- Check if ran today (local time)
    SELECT EXISTS(
        SELECT 1 FROM runs
        WHERE user_id = p_user_id AND start_date = check_date
    ) INTO has_run;

    -- If not today, check yesterday
    IF NOT has_run THEN
        check_date := check_date - 1;
        SELECT EXISTS(
            SELECT 1 FROM runs
            WHERE user_id = p_user_id AND start_date = check_date
        ) INTO has_run;

        IF NOT has_run THEN
            RETURN 0;  -- No run today or yesterday = no active streak
        END IF;
    END IF;

    -- Count consecutive days backwards
    WHILE has_run LOOP
        streak_count := streak_count + 1;
        check_date := check_date - 1;

        SELECT EXISTS(
            SELECT 1 FROM runs
            WHERE user_id = p_user_id AND start_date = check_date
        ) INTO has_run;
    END LOOP;

    RETURN streak_count;
END;
$$;

GRANT EXECUTE ON FUNCTION get_current_streak(UUID, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION get_current_streak(UUID, TEXT) TO service_role;

COMMENT ON FUNCTION get_current_streak IS 'Calculate current running streak (consecutive days with runs). Uses user timezone for accurate "today" calculation.';

-- =====================================================
-- FIX: get_streak_stats - accept timezone parameter
-- =====================================================

DROP FUNCTION IF EXISTS get_streak_stats(UUID);

CREATE OR REPLACE FUNCTION get_streak_stats(p_user_id UUID, p_timezone TEXT DEFAULT 'America/New_York')
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSON;
    current_streak INTEGER;
    longest_streak INTEGER := 0;
    longest_start DATE;
    longest_end DATE;
    streak_count INTEGER := 0;
    streak_start DATE;
    prev_date DATE;
    curr_date DATE;
BEGIN
    -- Get current streak using timezone-aware function
    SELECT get_current_streak(p_user_id, p_timezone) INTO current_streak;

    -- Calculate longest streak by iterating through all dates
    FOR curr_date IN
        SELECT DISTINCT start_date
        FROM runs
        WHERE user_id = p_user_id
        ORDER BY start_date
    LOOP
        IF prev_date IS NULL OR curr_date = prev_date + 1 THEN
            -- Continue or start streak
            IF prev_date IS NULL THEN
                streak_start := curr_date;
            END IF;
            streak_count := streak_count + 1;
        ELSE
            -- Gap found - check if previous streak was longest
            IF streak_count > longest_streak THEN
                longest_streak := streak_count;
                longest_start := streak_start;
                longest_end := prev_date;
            END IF;
            -- Start new streak
            streak_start := curr_date;
            streak_count := 1;
        END IF;
        prev_date := curr_date;
    END LOOP;

    -- Check final streak
    IF streak_count > longest_streak THEN
        longest_streak := streak_count;
        longest_start := streak_start;
        longest_end := prev_date;
    END IF;

    result := json_build_object(
        'current_streak', current_streak,
        'longest_streak', longest_streak,
        'longest_start', longest_start,
        'longest_end', longest_end
    );

    RETURN result;
END;
$$;

GRANT EXECUTE ON FUNCTION get_streak_stats(UUID, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION get_streak_stats(UUID, TEXT) TO service_role;

COMMENT ON FUNCTION get_streak_stats IS 'Get comprehensive streak statistics including current and longest streaks. Uses user timezone for accurate calculations.';

-- =====================================================
-- FIX: recalculate_user_stats - accept timezone parameter
-- =====================================================

DROP FUNCTION IF EXISTS recalculate_user_stats(UUID);

CREATE OR REPLACE FUNCTION recalculate_user_stats(p_user_id UUID, p_timezone TEXT DEFAULT 'America/New_York')
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
    v_today DATE := (NOW() AT TIME ZONE p_timezone)::DATE;
    v_year_start DATE := DATE_TRUNC('year', (NOW() AT TIME ZONE p_timezone))::DATE;
    v_month_start DATE := DATE_TRUNC('month', (NOW() AT TIME ZONE p_timezone))::DATE;
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

    -- Get current streak using timezone-aware function
    SELECT get_current_streak(p_user_id, p_timezone) INTO v_current_streak_days;

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

    -- Get longest streak stats using timezone-aware function
    SELECT get_streak_stats(p_user_id, p_timezone) INTO v_streak_stats;
    v_longest_streak_days := (v_streak_stats->>'longest_streak')::INTEGER;
    v_longest_streak_start := (v_streak_stats->>'longest_start')::DATE;
    v_longest_streak_end := (v_streak_stats->>'longest_end')::DATE;

    -- Calculate year-to-date totals (using local timezone year boundary)
    SELECT
        COALESCE(SUM(distance_km), 0)::NUMERIC(10,2),
        COUNT(*)::INTEGER
    INTO v_ytd_distance_km, v_ytd_runs
    FROM runs
    WHERE user_id = p_user_id
      AND start_date >= v_year_start
      AND start_date <= v_today;

    -- Calculate month-to-date totals (using local timezone month boundary)
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

GRANT EXECUTE ON FUNCTION recalculate_user_stats(UUID, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION recalculate_user_stats(UUID, TEXT) TO service_role;

COMMENT ON FUNCTION recalculate_user_stats IS 'Recalculates and stores all running statistics for a user. Uses user timezone for accurate date boundaries. Call after syncing runs.';
