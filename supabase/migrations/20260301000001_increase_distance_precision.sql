-- Increase distance_km precision from NUMERIC(10,3) to NUMERIC(10,5).
--
-- SmashRun API returns distances with 5 decimal places (e.g. 1.64145 km),
-- but NUMERIC(10,3) truncates to 3 decimals (1.641 km). The ~1 meter/run
-- truncation error accumulates: over 31 runs in a month it can total 30+
-- meters, enough to make a 100-mile month appear as 99.98 miles.
--
-- This is a safe ALTER: widening precision never loses existing data.
-- Views that reference distance_km must be dropped and recreated.

-- Drop dependent views
DROP VIEW IF EXISTS daily_summary;
DROP VIEW IF EXISTS monthly_summary;

-- runs table: primary distance field
ALTER TABLE runs
    ALTER COLUMN distance_km TYPE NUMERIC(10, 5);

-- splits table: cumulative distance field
ALTER TABLE splits
    ALTER COLUMN cumulative_distance_km TYPE NUMERIC(10, 5);

-- Recreate views
CREATE VIEW daily_summary AS
SELECT
    user_id,
    start_date,
    COUNT(*) AS run_count,
    SUM(distance_km) AS total_km,
    AVG(distance_km) AS avg_km,
    AVG(average_pace_min_per_km) AS avg_pace,
    MIN(start_date_time_local) AS first_run,
    MAX(start_date_time_local) AS last_run
FROM runs
GROUP BY user_id, start_date
ORDER BY user_id, start_date DESC;

CREATE VIEW monthly_summary AS
SELECT
    user_id,
    start_year,
    start_month,
    TO_DATE(start_year || '-' || start_month || '-01', 'YYYY-MM-DD') AS month_start,
    COUNT(*) AS run_count,
    SUM(distance_km) AS total_km,
    AVG(distance_km) AS avg_km,
    MAX(distance_km) AS longest_run_km,
    AVG(average_pace_min_per_km) AS avg_pace
FROM runs
GROUP BY user_id, start_year, start_month
ORDER BY user_id, start_year DESC, start_month DESC;

COMMENT ON VIEW daily_summary IS 'Daily statistics per user';
COMMENT ON VIEW monthly_summary IS 'Monthly statistics per user';
