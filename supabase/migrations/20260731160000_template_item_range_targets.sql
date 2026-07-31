-- Range targets on template_items (SB-446): reps, load and rest.
--
-- Matthew prescribes ranges, not fixed numbers. SB-264 gave duration a min/max
-- pair; every other dimension was still a single scalar, so the 2026-07-30
-- speed-endurance block could not be represented at all:
--
--   "8-12x200 at 40-42 seconds"        -> rep-count range
--   "60-90 second rest (go off how you feel)" -> rest range, autoregulated
--   "Full recovery before ground-to-sprint accelerations" -> rest with no number
--   "Lateral arm raise (5-8lb dumbbells)"     -> load range
--
-- The existing columns become the LOWER bound when the `_max` twin is set,
-- matching the convention SB-264 established for duration. All additive and
-- nullable: existing templates and the create path are untouched.

ALTER TABLE template_items
    ADD COLUMN target_reps_max INTEGER,
    ADD COLUMN target_load_max_kg NUMERIC(6, 2),
    ADD COLUMN rest_seconds_max NUMERIC(8, 2),
    ADD COLUMN rest_mode TEXT;

-- "Full recovery" and "go off how you feel" are prescriptions, not numbers.
-- Storing them as a mode keeps the sheet honest instead of inventing a value
-- the coach never gave.
ALTER TABLE template_items
    ADD CONSTRAINT template_items_rest_mode_check
    CHECK (rest_mode IS NULL OR rest_mode IN ('fixed', 'range', 'full', 'autoregulated'));

-- A max below its min is a data-entry error that would render as "12-8 reps".
ALTER TABLE template_items
    ADD CONSTRAINT template_items_reps_range_check
    CHECK (target_reps_max IS NULL OR target_reps IS NULL OR target_reps_max >= target_reps),
    ADD CONSTRAINT template_items_load_range_check
    CHECK (target_load_max_kg IS NULL OR target_load_kg IS NULL OR target_load_max_kg >= target_load_kg),
    ADD CONSTRAINT template_items_rest_range_check
    CHECK (rest_seconds_max IS NULL OR rest_seconds IS NULL OR rest_seconds_max >= rest_seconds);

COMMENT ON COLUMN template_items.target_reps_max IS
    'Upper bound when reps are a range ("8-12"); target_reps is the lower bound.';
COMMENT ON COLUMN template_items.target_load_max_kg IS
    'Upper bound when load is a range ("5-8lb dumbbells"); target_load_kg is the lower bound.';
COMMENT ON COLUMN template_items.rest_seconds_max IS
    'Upper bound when rest is a range ("60-90 seconds"); rest_seconds is the lower bound.';
COMMENT ON COLUMN template_items.rest_mode IS
    'How rest is prescribed: fixed | range | full (full recovery) | autoregulated (go off how you feel).';
