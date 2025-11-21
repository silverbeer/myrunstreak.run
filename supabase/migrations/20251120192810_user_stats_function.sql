-- Migration: Add database function for user statistics aggregation
-- This avoids PostgREST row limits by doing aggregation server-side

-- Function to get overall user statistics
CREATE OR REPLACE FUNCTION get_user_stats(p_user_id UUID)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_build_object(
        'total_runs', COUNT(*),
        'total_km', COALESCE(ROUND(SUM(distance_km)::numeric, 2), 0),
        'avg_km', COALESCE(ROUND(AVG(distance_km)::numeric, 2), 0),
        'longest_run_km', COALESCE(ROUND(MAX(distance_km)::numeric, 2), 0),
        'avg_pace_min_per_km', COALESCE(
            ROUND(AVG(average_pace_min_per_km)::numeric, 2),
            0
        )
    )
    INTO result
    FROM runs
    WHERE user_id = p_user_id;

    RETURN result;
END;
$$;

-- Grant execute permission to authenticated users and service role
GRANT EXECUTE ON FUNCTION get_user_stats(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION get_user_stats(UUID) TO service_role;

COMMENT ON FUNCTION get_user_stats IS 'Get aggregated running statistics for a user. Returns total runs, distance, averages, and records.';

-- Function to calculate current running streak
CREATE OR REPLACE FUNCTION get_current_streak(p_user_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    streak_count INTEGER := 0;
    check_date DATE;
    has_run BOOLEAN;
BEGIN
    -- Start from today
    check_date := CURRENT_DATE;

    -- Check if ran today
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

GRANT EXECUTE ON FUNCTION get_current_streak(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION get_current_streak(UUID) TO service_role;

COMMENT ON FUNCTION get_current_streak IS 'Calculate current running streak (consecutive days with runs).';

-- Function to get all streak information including longest streak
CREATE OR REPLACE FUNCTION get_streak_stats(p_user_id UUID)
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
    -- Get current streak first
    SELECT get_current_streak(p_user_id) INTO current_streak;

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

GRANT EXECUTE ON FUNCTION get_streak_stats(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION get_streak_stats(UUID) TO service_role;

COMMENT ON FUNCTION get_streak_stats IS 'Get comprehensive streak statistics including current and longest streaks.';
