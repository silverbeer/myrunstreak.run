-- =====================================================
-- Broken reps: segment goals + pace ranges (SB-264)
-- =====================================================
-- Matthew prescribes reps like "400m broken into 100m sections" with a goal
-- range per section (0-100: 20-22s, 100-200: 15s, ...). Two additions:
--
--   target_duration_max_seconds  upper bound of a goal range; existing
--                                target_duration_seconds becomes the lower
--                                bound when both are set.
--   segments                     JSONB list of per-segment goals for one rep:
--                                [{"distance_m":100,"target_s_min":20,"target_s_max":22}, ...]
--
-- Actuals (the REALITY side) reuse exercise_sets.extra JSONB:
--   extra.segments = [{"distance_m":100,"time_s":21,"note":null}, ...]
-- so no schema change is needed on the logging side.

ALTER TABLE template_items ADD COLUMN target_duration_max_seconds NUMERIC(8, 2);
ALTER TABLE template_items ADD COLUMN segments JSONB;

COMMENT ON COLUMN template_items.target_duration_max_seconds IS
    'Upper bound of a goal time range (SB-264); target_duration_seconds is the lower bound';
COMMENT ON COLUMN template_items.segments IS
    'Per-segment goals for a broken rep: [{distance_m, target_s_min, target_s_max, label?}]';

-- ---- seed: movements from Matthew's Thursday track session not yet in the library ----
INSERT INTO exercises
    (key, display_name, category, measures, is_benchmark, movement_pattern,
     equipment, body_region, laterality, difficulty, aliases, cues, instructions)
VALUES
('paced_strides', 'Paced strides', 'speed', ARRAY['reps','distance_m'], FALSE, 'sprint',
 ARRAY['none'], ARRAY['lower','full'], 'bilateral', 'beginner',
 ARRAY['strides','striders'],
 ARRAY['Smooth build to ~85% speed','Relax and float, quick turnover'], NULL),
('bounding', 'Bounding', 'power', ARRAY['reps','distance_m'], FALSE, 'jump',
 ARRAY['none'], ARRAY['lower','full'], 'bilateral', 'intermediate',
 ARRAY['bounding starts','bounds'],
 ARRAY['Exaggerated running leaps','Drive the knee, hang in the air'], NULL),
('backward_run', 'Backward run', 'speed', ARRAY['duration_s','distance_m'], FALSE, 'sprint',
 ARRAY['none'], ARRAY['lower'], 'bilateral', 'beginner',
 ARRAY['backwards running','retro running','running backward'],
 ARRAY['Small quick steps, stay on the balls of the feet','Lean slightly forward, arms drive'], NULL),
('interval_run', 'Interval run', 'speed', ARRAY['distance_m','time_s'], TRUE, 'sprint',
 ARRAY['none'], ARRAY['lower','full'], 'bilateral', 'intermediate',
 ARRAY['track interval','repeat','rep'],
 ARRAY['Fixed distance at prescribed pace','Recover fully between reps'], NULL)
ON CONFLICT (key) DO NOTHING;
