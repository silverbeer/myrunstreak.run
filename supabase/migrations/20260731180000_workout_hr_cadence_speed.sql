-- Heart rate, cadence and speed as first-class workout measures (SB-447).
--
-- The 2026-07-30 plan is the first to prescribe them, and the coach asked for
-- instrumentation directly: "insert as many metrics as you can ---> adjust,
-- assess. I'll be there for it."
--
--   Bike intervals: 2 min on / 1 min recovery, "on" pace = HR 160-175
--   No HR monitor:  170 rpm or 20 mph
--   Aerobic day:    keep HR 120-145
--
-- None of it existed anywhere. Putting it in `extra` JSONB would mean no
-- trending, no review, no charts — which defeats the instruction.
--
-- Speed is stored canonical kph and displayed as mph at the edge, the same
-- convention as kg/lb.
--
-- CADENCE IS DELIBERATELY UNIT-AGNOSTIC. The ticket proposed `cadence_rpm`, but
-- the prescribed 170 is not sustainable bike cadence (elite is ~100-120) — it
-- is textbook *running* cadence in steps per minute. Rather than bake in a unit
-- that is wrong for half the movements, the column is a per-minute count whose
-- unit follows the exercise: crank revolutions on a bike, steps running, skips
-- on a rope. Open question for Matthew either way.

ALTER TABLE exercise_sets
    ADD COLUMN hr_bpm_avg INTEGER,
    ADD COLUMN hr_bpm_max INTEGER,
    ADD COLUMN cadence NUMERIC(5, 1),
    ADD COLUMN speed_kph NUMERIC(5, 2);

ALTER TABLE template_items
    ADD COLUMN target_hr_min INTEGER,
    ADD COLUMN target_hr_max INTEGER,
    ADD COLUMN target_cadence NUMERIC(5, 1),
    ADD COLUMN target_speed_kph NUMERIC(5, 2);

-- Bounds catch data-entry accidents (a transposed 610 bpm), not implausible
-- coaching. The "is 170 cadence realistic" judgement stays advisory in the
-- log-workout skill, which already flags outliers to a human — a hard limit
-- there would reject every one of Matthew's sessions before he confirms.
ALTER TABLE exercise_sets
    ADD CONSTRAINT exercise_sets_hr_avg_check
    CHECK (hr_bpm_avg IS NULL OR hr_bpm_avg BETWEEN 20 AND 250),
    ADD CONSTRAINT exercise_sets_hr_max_check
    CHECK (hr_bpm_max IS NULL OR hr_bpm_max BETWEEN 20 AND 250),
    ADD CONSTRAINT exercise_sets_hr_order_check
    CHECK (hr_bpm_max IS NULL OR hr_bpm_avg IS NULL OR hr_bpm_max >= hr_bpm_avg),
    ADD CONSTRAINT exercise_sets_cadence_check
    CHECK (cadence IS NULL OR cadence BETWEEN 0 AND 300),
    ADD CONSTRAINT exercise_sets_speed_check
    CHECK (speed_kph IS NULL OR speed_kph BETWEEN 0 AND 100);

ALTER TABLE template_items
    ADD CONSTRAINT template_items_hr_min_check
    CHECK (target_hr_min IS NULL OR target_hr_min BETWEEN 20 AND 250),
    ADD CONSTRAINT template_items_hr_max_check
    CHECK (target_hr_max IS NULL OR target_hr_max BETWEEN 20 AND 250),
    ADD CONSTRAINT template_items_hr_range_check
    CHECK (target_hr_max IS NULL OR target_hr_min IS NULL OR target_hr_max >= target_hr_min),
    ADD CONSTRAINT template_items_cadence_check
    CHECK (target_cadence IS NULL OR target_cadence BETWEEN 0 AND 300),
    ADD CONSTRAINT template_items_speed_check
    CHECK (target_speed_kph IS NULL OR target_speed_kph BETWEEN 0 AND 100);

COMMENT ON COLUMN exercise_sets.cadence IS
    'Per-minute count; unit follows the movement — crank rpm cycling, steps running, skips on a rope.';
COMMENT ON COLUMN exercise_sets.speed_kph IS 'Canonical kph; displayed as mph at the edge.';
COMMENT ON COLUMN template_items.target_hr_min IS 'Lower bound of a prescribed HR zone ("HR 160-175").';
COMMENT ON COLUMN template_items.target_cadence IS
    'Per-minute count; unit follows the movement, as for exercise_sets.cadence.';

-- The bike was seeded (SB-445) with only duration/distance because these
-- measures did not exist. It is the movement the whole aerobic day is
-- prescribed by heart rate on, so give it the full set now.
UPDATE exercises
SET measures = ARRAY['duration_s', 'distance_m', 'hr_bpm', 'cadence', 'speed_kph']
WHERE key = 'bike';

-- The other movements the 2026-07-30 plan drives by heart rate.
UPDATE exercises
SET measures = array_append(measures, 'hr_bpm')
WHERE key IN ('easy_jog', 'interval_run', 'jump_rope')
  AND NOT ('hr_bpm' = ANY (measures));
