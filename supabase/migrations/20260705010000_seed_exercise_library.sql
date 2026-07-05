-- =====================================================
-- Seed the canonical exercise library from Matthew's workouts (SB-228)
-- =====================================================
-- Real movements from Gabe's Monday / Saturday-home / Saturday-track sessions,
-- so the catalog is populated the moment a coach opens it. All public/canonical
-- (owner_id NULL, visibility defaults 'public'). Idempotent via ON CONFLICT.
--
-- measures use the catalog vocabulary: reps, duration_s, load_kg, distance_m, time_s.
-- Loads are noted in lb in the plans; the app stores canonical kg and converts
-- at the input/display edge.
-- =====================================================

INSERT INTO exercises
    (key, display_name, category, measures, is_benchmark, movement_pattern,
     equipment, body_region, laterality, difficulty, aliases, cues, instructions)
VALUES
-- ---- Speed work + sprint drills ----
('100m_fly', '100m fly', 'speed', ARRAY['time_s'], TRUE, 'sprint',
 ARRAY['none'], ARRAY['lower','full'], 'bilateral', 'advanced',
 ARRAY['100 fly','flying 100'],
 ARRAY['Running start on the curve','Pass the 100m mark at/near full speed'], NULL),
('three_step_start', '3-step start', 'speed', ARRAY['reps','distance_m'], FALSE, 'sprint',
 ARRAY['none'], ARRAY['lower','full'], 'bilateral', 'intermediate',
 ARRAY['three step start','3 step starts'],
 ARRAY['Ground start, driving phase','Head down, accelerate the first 5 steps'], NULL),
('four_point_start', '4-point start', 'speed', ARRAY['reps'], FALSE, 'sprint',
 ARRAY['none'], ARRAY['lower','full'], 'bilateral', 'intermediate',
 ARRAY['sprint start','4 point start','crouched start'],
 ARRAY['Explode from a crouched stance','First 3–5 steps at max acceleration'], NULL),
('high_knees', 'High knees', 'speed', ARRAY['duration_s','distance_m'], FALSE, 'sprint',
 ARRAY['none'], ARRAY['lower'], 'bilateral', 'beginner',
 ARRAY['high knee drill'], ARRAY['Drive knees to hip height','Quick ground contact, stay tall'], NULL),
('butt_kicks', 'Butt kicks', 'speed', ARRAY['duration_s','distance_m'], FALSE, 'sprint',
 ARRAY['none'], ARRAY['lower'], 'bilateral', 'beginner',
 ARRAY['heel kicks'], ARRAY['Heels to glutes','Stay tall, quick turnover'], NULL),
('karaoke', 'Karaoke', 'speed', ARRAY['duration_s','distance_m'], FALSE, 'other',
 ARRAY['none'], ARRAY['lower','full'], 'bilateral', 'beginner',
 ARRAY['carioca','grapevine'], ARRAY['Cross over front and back','Open the hips, stay light'], NULL),
('a_skips', 'A-skips', 'speed', ARRAY['duration_s','distance_m'], FALSE, 'sprint',
 ARRAY['none'], ARRAY['lower'], 'bilateral', 'intermediate',
 ARRAY['a skip'], ARRAY['Knee up, toe up, heel up','Rhythmic skip'], NULL),
('b_skips', 'B-skips', 'speed', ARRAY['duration_s','distance_m'], FALSE, 'sprint',
 ARRAY['none'], ARRAY['lower'], 'bilateral', 'intermediate',
 ARRAY['b skip'], ARRAY['A-skip then paw the ground','Extend and pull through'], NULL),
('skywalker', 'Skywalker', 'mobility', ARRAY['reps','duration_s'], FALSE, 'other',
 ARRAY['none'], ARRAY['lower'], 'unilateral', 'intermediate',
 ARRAY[]::text[], ARRAY[]::text[],
 'Coach warm-up drill — two variations. Exact movement TBD (confirm with Matthew).'),
('easy_jog', 'Easy jog', 'cardio', ARRAY['duration_s','distance_m'], FALSE, 'other',
 ARRAY['none'], ARRAY['full'], 'bilateral', 'beginner',
 ARRAY['jog','easy run','warm-up jog'], ARRAY['Conversational pace'], NULL),
('dynamic_drills', 'Dynamic warm-up drills', 'mobility', ARRAY['duration_s'], FALSE, 'mobility',
 ARRAY['none'], ARRAY['full'], 'bilateral', 'beginner',
 ARRAY['warm-up drills','warmup drills'],
 ARRAY['High knees, butt kicks, karaoke, A/B skips'], NULL),

-- ---- Core / stability ----
('side_plank', 'Side plank', 'strength', ARRAY['duration_s'], FALSE, 'isometric',
 ARRAY['bodyweight'], ARRAY['core'], 'unilateral', 'beginner',
 ARRAY['left plank','right plank','l side plank','r side plank','plank left','plank right'],
 ARRAY['Stack shoulder over elbow','Hips high, straight line'], NULL),
('reverse_plank', 'Reverse (back) plank', 'strength', ARRAY['duration_s'], FALSE, 'isometric',
 ARRAY['bodyweight'], ARRAY['core','posterior'], 'bilateral', 'intermediate',
 ARRAY['back plank','reverse plank'], ARRAY['Face up, hips lifted','Drive the heels down'], NULL),
('bird_dog', 'Bird dog', 'mobility', ARRAY['reps','duration_s'], FALSE, 'anti_rotation',
 ARRAY['bodyweight'], ARRAY['core'], 'unilateral', 'beginner',
 ARRAY['bird-dog'], ARRAY['Opposite arm and leg','Keep hips level — no rotation'], NULL),
('aquaman', 'Aquaman', 'mobility', ARRAY['duration_s','reps'], FALSE, 'anti_rotation',
 ARRAY['bodyweight'], ARRAY['core','posterior'], 'unilateral', 'beginner',
 ARRAY['swimmers','opposite superman'], ARRAY['Prone: lift opposite arm + leg','Long through the spine'], NULL),
('superman', 'Superman', 'mobility', ARRAY['duration_s','reps'], FALSE, 'isometric',
 ARRAY['bodyweight'], ARRAY['core','posterior'], 'bilateral', 'beginner',
 ARRAY['superman hold'], ARRAY['Prone: lift arms and legs','Squeeze glutes and back'], NULL),
('russian_twists', 'Russian twists', 'strength', ARRAY['duration_s','reps'], FALSE, 'rotation',
 ARRAY['bodyweight'], ARRAY['core'], 'bilateral', 'beginner',
 ARRAY['russian twist'], ARRAY['Rotate the shoulders, not just the arms','Feet up to progress'], NULL),
('bear_crawl', 'Bear crawl', 'strength', ARRAY['duration_s','distance_m'], FALSE, 'other',
 ARRAY['bodyweight'], ARRAY['full','core'], 'bilateral', 'beginner',
 ARRAY['bear crawls'], ARRAY['Knees under hips, hovering','Move opposite hand and foot'], NULL),
('crab_walk', 'Crab walk', 'strength', ARRAY['duration_s','distance_m'], FALSE, 'other',
 ARRAY['bodyweight'], ARRAY['full','posterior'], 'bilateral', 'beginner',
 ARRAY['crab walks'], ARRAY['Hips up','Walk the hands and feet'], NULL),

-- ---- Squat / lower / explosive ----
('sumo_squat', 'Sumo squat', 'strength', ARRAY['reps','duration_s'], FALSE, 'squat',
 ARRAY['bodyweight'], ARRAY['lower'], 'bilateral', 'beginner',
 ARRAY['sumo squats','wide squat'], ARRAY['Wide stance, toes out','Knees track over toes'], NULL),
('jump_squat', 'Jump squat', 'power', ARRAY['reps'], FALSE, 'jump',
 ARRAY['bodyweight'], ARRAY['lower'], 'bilateral', 'intermediate',
 ARRAY['jump squats','squat jump'], ARRAY['Explode up through the floor','Land soft, absorb'], NULL),
('cannonball', 'Cannonball', 'strength', ARRAY['reps','duration_s'], FALSE, 'squat',
 ARRAY['bodyweight'], ARRAY['lower','full'], 'bilateral', 'beginner',
 ARRAY[]::text[], ARRAY['Feet together','Stand tall between reps'],
 'Feet together; bend down into a tucked cannonball position while standing, then come straight back up to full standing.'),
('step_up_max_jump', 'Step-up max jumps', 'power', ARRAY['reps'], FALSE, 'jump',
 ARRAY['box'], ARRAY['lower'], 'unilateral', 'advanced',
 ARRAY['step up jumps','box step-up jump'], ARRAY['Drive off the box','Max height'],
 'Height variants (use the variant field): 45° mid-shin, 90° knee, 135° mid-thigh.'),
('burpees', 'Burpees', 'cardio', ARRAY['reps','duration_s'], FALSE, 'other',
 ARRAY['bodyweight'], ARRAY['full'], 'bilateral', 'beginner',
 ARRAY['burpee'], ARRAY['Chest to the floor','Jump at the top'], NULL),

-- ---- Carry / dumbbell arm work ----
('farmers_carry', 'Farmer''s carry', 'strength', ARRAY['duration_s','distance_m','load_kg'], FALSE, 'carry',
 ARRAY['dumbbell'], ARRAY['full','grip'], 'bilateral', 'beginner',
 ARRAY['farmer carry','farmers walk'], ARRAY['Tall posture, braced core','Even weight in both hands'], NULL),
('bicep_curl', 'Bicep curls', 'strength', ARRAY['reps','duration_s','load_kg'], FALSE, 'pull',
 ARRAY['dumbbell'], ARRAY['upper'], 'bilateral', 'beginner',
 ARRAY['bicep curl','biceps curl'], ARRAY['Elbows pinned to the sides','Control the lowering'], NULL),
('tricep_extension', 'Tricep extension', 'strength', ARRAY['reps','duration_s','load_kg'], FALSE, 'push',
 ARRAY['dumbbell'], ARRAY['upper'], 'bilateral', 'beginner',
 ARRAY['tricep ext','triceps extension'], ARRAY['Elbows in','Full lockout at the top'], NULL),
('lateral_raise', 'Lateral arm raise', 'strength', ARRAY['reps','duration_s','load_kg'], FALSE, 'push',
 ARRAY['dumbbell'], ARRAY['upper'], 'bilateral', 'beginner',
 ARRAY['lateral raises','side raise','lateral arm raise or hold'],
 ARRAY['Lead with the elbows','Stop at shoulder height (or hold)'], NULL),
('front_raise', 'Front arm raise', 'strength', ARRAY['reps','load_kg'], FALSE, 'push',
 ARRAY['dumbbell'], ARRAY['upper'], 'bilateral', 'beginner',
 ARRAY['front raises','frontal arm raise','front arm raise'],
 ARRAY['Raise to shoulder height','Slight bend in the elbows'], NULL)
ON CONFLICT (key) DO NOTHING;

-- ---- Aliases on existing canonical rows (fold Matthew's varied wording) ----
UPDATE exercises SET aliases = ARRAY['front plank','plank front'] WHERE key = 'plank';
UPDATE exercises SET aliases = ARRAY['forward lunge','split squat','walking lunges','lunges']
    WHERE key = 'lunge';
UPDATE exercises SET aliases = ARRAY['forty','40 yard dash','40-yard sprint']
    WHERE key = '40yd_dash';
