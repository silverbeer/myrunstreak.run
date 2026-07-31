-- =====================================================
-- Seed the 9 movements Matthew's 2026-07-30 plan introduced (SB-445)
-- =====================================================
-- The plan (speed-endurance + upper/lower 30s circuits + an in-season aerobic
-- day) references movements the catalog has never held, so those sessions
-- cannot be built as templates at all. All canonical/public (owner_id NULL,
-- visibility defaults 'public'), idempotent via ON CONFLICT, following
-- 20260705010000_seed_exercise_library.sql.
--
-- measures use the catalog vocabulary: reps, duration_s, load_kg, distance_m,
-- time_s. Loads are prescribed in lb; the app stores canonical kg and converts
-- at the input/display edge.
--
-- Aliases are deliberately sparse. Since SB-454 the matcher folds case,
-- punctuation, hyphens, apostrophes and plurals, so "pull ups" already finds
-- "Pull-up" — an alias that only differs by those is a no-op the audit reports
-- as redundant. Aliases here carry wording the fold *cannot* reach ("wall squat
-- hold" for a wall sit). They also feed the create/publish duplicate guard, so
-- an alias is never a near-synonym that would block a genuinely distinct row.
-- =====================================================

INSERT INTO exercises
    (key, display_name, category, measures, is_benchmark, movement_pattern,
     equipment, body_region, laterality, difficulty, aliases, cues, instructions)
VALUES
-- ---- Upper cycle ----
('pull_up', 'Pull-up', 'strength', ARRAY['reps','duration_s'], FALSE, 'pull',
 ARRAY['pull_up_bar'], ARRAY['upper'], 'bilateral', 'intermediate',
 ARRAY['hang','dead hang'],
 ARRAY['Full hang at the bottom','Chin clears the bar','Control the lowering'],
 'Prescribed as "pull-up (or hang)": when reps are not there yet, hold the hang '
 'for the same work period and log duration_s instead of reps.'),

('bent_over_row', 'Bent-over row', 'strength', ARRAY['reps','duration_s','load_kg'], FALSE, 'pull',
 ARRAY['dumbbell'], ARRAY['upper'], 'bilateral', 'beginner',
 ARRAY['db row','dumbbell row'],
 ARRAY['Hinge at the hips, flat back','Pull to the ribs, elbows past the torso'],
 'The dynamic row. Distinct from `row_hold`, which is the isometric hold at the '
 'top of the same position.'),

('shoulder_press', 'Shoulder press', 'strength', ARRAY['reps','duration_s','load_kg'], FALSE, 'push',
 ARRAY['dumbbell'], ARRAY['upper'], 'bilateral', 'beginner',
 ARRAY['overhead press','db shoulder press'],
 ARRAY['Press overhead without arching the low back','Ribs down, core braced'], NULL),

-- ---- Lower cycle ----
('calf_raise_single_leg', 'Single-leg calf raise', 'strength',
 ARRAY['reps','duration_s','load_kg'], FALSE, 'other',
 ARRAY['bodyweight'], ARRAY['lower'], 'unilateral', 'beginner',
 ARRAY['1 legged calf raise','one legged calf raise','heel raise'],
 ARRAY['Full stretch at the bottom, full extension at the top','Slow on the way down'],
 'Unilateral — set `variant` to left/right on the template item.'),

('wall_sit', 'Wall sit', 'strength', ARRAY['duration_s','load_kg'], FALSE, 'isometric',
 ARRAY['wall'], ARRAY['lower'], 'bilateral', 'beginner',
 ARRAY['wall squat hold','wall squat'],
 ARRAY['Thighs parallel to the floor','Back flat against the wall','Weight in the heels'], NULL),

('pistol_squat', 'Pistol squat', 'strength', ARRAY['reps','duration_s','load_kg'], FALSE, 'squat',
 ARRAY['bodyweight'], ARRAY['lower'], 'unilateral', 'advanced',
 ARRAY['single leg squat','one legged squat'],
 ARRAY['Free leg extended forward','Descend under control, no collapse at the bottom'],
 'Advanced — regress to a box/bench pistol or a supported version until the full '
 'range is there. Set `variant` to left/right on the template item.'),

('nordic_curl', 'Nordic curl', 'strength', ARRAY['reps'], FALSE, 'hinge',
 ARRAY['anchor','partner'], ARRAY['lower'], 'bilateral', 'advanced',
 ARRAY['nordic hamstring curl','natural glute ham raise'],
 ARRAY['Hips extended the whole way down','Lower as slowly as possible, catch with the hands'],
 'Needs the ankles anchored — a partner holding them, or a loaded bar/couch edge. '
 'Confirm with Matthew what Gabe is anchoring against at home.'),

-- ---- Speed-endurance ----
('ground_start_accel', 'Ground-to-sprint acceleration', 'speed',
 ARRAY['reps','distance_m','time_s'], FALSE, 'sprint',
 ARRAY['none'], ARRAY['lower','full'], 'bilateral', 'intermediate',
 ARRAY['ground start','ground to sprint','get up and go'],
 ARRAY['Full recovery between reps — this is a speed drill, not conditioning',
       'Get up and accelerate in one motion'],
 'Prescribed at 10yd from four start positions (back, stomach, knees, butt). '
 'Set `variant` on the template item to the position used.'),

-- ---- In-season aerobic day ----
('bike', 'Bike', 'cardio', ARRAY['duration_s','distance_m'], FALSE, 'other',
 ARRAY['bike'], ARRAY['lower','full'], 'bilateral', 'beginner',
 ARRAY['stationary bike','cycling','bike intervals'],
 ARRAY['Steady effort on the aerobic day','On the intervals, the "on" is genuinely hard'],
 'First bike prescription in any plan. The 2026-07-30 session drives it by heart '
 'rate (160-175 on the intervals, 120-145 steady) with a cadence/speed fallback '
 '(170 rpm or 20 mph) — none of which the measures vocabulary can hold yet. '
 'Seeded with duration/distance now; enrich once SB-447 lands HR, cadence and speed.')
ON CONFLICT (key) DO NOTHING;
