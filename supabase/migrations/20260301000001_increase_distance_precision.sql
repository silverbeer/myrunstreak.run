-- Increase distance_km precision from NUMERIC(10,3) to NUMERIC(10,5).
--
-- SmashRun API returns distances with 5 decimal places (e.g. 1.64145 km),
-- but NUMERIC(10,3) truncates to 3 decimals (1.641 km). The ~1 meter/run
-- truncation error accumulates: over 31 runs in a month it can total 30+
-- meters, enough to make a 100-mile month appear as 99.98 miles.
--
-- This is a safe ALTER: widening precision never loses existing data.

-- runs table: primary distance field
ALTER TABLE runs
    ALTER COLUMN distance_km TYPE NUMERIC(10, 5);

-- splits table: cumulative distance field
ALTER TABLE splits
    ALTER COLUMN cumulative_distance_km TYPE NUMERIC(10, 5);
