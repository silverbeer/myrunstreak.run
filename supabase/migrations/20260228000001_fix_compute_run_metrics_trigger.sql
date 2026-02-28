-- Migration: Fix compute_run_metrics trigger to not override Python-calculated dates
--
-- Problem: The trigger recalculates start_date, start_year, start_month, and
-- start_day_of_week from start_date_time_local (TIMESTAMPTZ). Because TIMESTAMPTZ
-- stores values in UTC internally, DATE() extracts the UTC date, not the user's
-- local date. For evening runs (after ~7pm EST), this can produce the WRONG date.
--
-- Fix: Remove date field recalculations from the trigger. The Python mapper
-- (mappers.py:activity_to_run_dict) already correctly extracts the local date
-- from the activity's local datetime BEFORE any timezone conversion.
-- Keep only the pace/speed calculations which are timezone-independent.
--
-- Related: GitHub Issue #31

CREATE OR REPLACE FUNCTION compute_run_metrics()
RETURNS TRIGGER AS $$
BEGIN
    -- Compute pace and speed (timezone-independent calculations)
    -- Date fields (start_date, start_year, start_month, start_day_of_week)
    -- are set correctly by the Python mapper using the activity's local datetime.
    -- We do NOT override them here because DATE(TIMESTAMPTZ) extracts the UTC date,
    -- which can differ from the user's local date for evening runs.
    IF NEW.duration_seconds > 0 AND NEW.distance_km > 0 THEN
        NEW.average_pace_min_per_km := NEW.duration_seconds / 60.0 / NEW.distance_km;
        NEW.average_speed_kph := NEW.distance_km / (NEW.duration_seconds / 3600.0);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION compute_run_metrics IS 'Compute derived pace/speed metrics on insert/update. Date fields are set by the Python mapper.';
