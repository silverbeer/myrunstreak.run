-- =====================================================
-- Athlete Training Tracker — structured workouts (SB-190)
-- =====================================================
-- Records structured S&C workouts: a coach's template, logged sessions, and the
-- per-exercise sets actually performed. Additive — the metric_* tables are
-- untouched. Mirrors the running pattern (session -> measurements -> progress):
-- a workout_session is like a run, exercise_sets are like splits (timed
-- segments + rest gaps via started_at/ended_at).
--
--   exercises          global catalog of movements (like metric_types)
--   workout_templates  a coach's prescribed plan + template_items
--   workout_sessions   a logged session (per athlete user)
--   exercise_sets      the ACTUAL performance — the heart of progress
--
-- Heterogeneous measures: each exercise fills only the dimension columns it uses
-- (reps | duration_seconds | load_kg | distance_m | time_seconds) — same wide-
-- nullable approach as the splits table. Performance tests (40yd dash, vertical)
-- live here too: fixed distance, measured time, trended over the season.
--
-- RLS: per-user tables are STRICT (user_id = auth.uid()), no anon escape.
-- exercises is a public read-only catalog.
-- =====================================================

-- ===== Enums =====
CREATE TYPE exercise_category AS ENUM ('strength', 'speed', 'power', 'mobility', 'cardio', 'test');
CREATE TYPE workout_type AS ENUM ('circuit', 'intervals', 'test', 'session');

-- =====================================================
-- exercises — global catalog (writes via migrations / service role only)
-- =====================================================
CREATE TABLE exercises (
    key TEXT PRIMARY KEY,                        -- slug: pushups, 40yd_dash, plank
    display_name TEXT NOT NULL,
    category exercise_category NOT NULL,
    measures TEXT[] NOT NULL DEFAULT '{}',       -- dims used: reps,duration_s,load_kg,distance_m,time_s
    is_benchmark BOOLEAN NOT NULL DEFAULT FALSE, -- TRUE for tracked tests (40yd, vertical, broad)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE exercises IS 'Global catalog of movements; category test + is_benchmark flag the speed/power progress markers';
COMMENT ON COLUMN exercises.measures IS 'Which dimensions this exercise records: reps,duration_s,load_kg,distance_m,time_s';

INSERT INTO exercises (key, display_name, category, measures, is_benchmark) VALUES
    ('40yd_dash',     '40-yard dash',        'test',     ARRAY['distance_m','time_s'],          TRUE),
    ('vertical_jump', 'Vertical jump',       'test',     ARRAY['distance_m'],                   TRUE),
    ('broad_jump',    'Broad jump',          'test',     ARRAY['distance_m'],                   TRUE),
    ('pro_agility',   '5-10-5 pro agility',  'test',     ARRAY['time_s'],                       TRUE),
    ('pushups',       'Push-ups',            'strength', ARRAY['reps','duration_s'],            FALSE),
    ('plank',         'Plank',               'strength', ARRAY['duration_s'],                   FALSE),
    ('jump_rope',     'Jump rope',           'cardio',   ARRAY['duration_s'],                   FALSE),
    ('lunge',         'Lunges',              'strength', ARRAY['reps'],                         FALSE),
    ('frog_jump',     'Frog jumps',          'power',    ARRAY['reps','distance_m','time_s'],   FALSE),
    ('hill_sprint',   'Hill sprint',         'speed',    ARRAY['duration_s','distance_m'],      FALSE),
    ('bicep_hold',    'Bicep 90° hold',      'strength', ARRAY['duration_s','load_kg'],         FALSE),
    ('row_hold',      'Bent-over row hold',  'strength', ARRAY['duration_s','load_kg'],         FALSE),
    ('back_bridge',   'Back bridge',         'mobility', ARRAY['duration_s'],                   FALSE);

-- =====================================================
-- workout_templates — a coach's prescribed plan
-- =====================================================
CREATE TABLE workout_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name TEXT NOT NULL,                          -- "Take-home #1", "Saturday Circuit"
    type workout_type NOT NULL DEFAULT 'circuit',
    rounds INTEGER NOT NULL DEFAULT 1 CHECK (rounds >= 1),
    source TEXT,                                 -- coach name, e.g. "Matthew"
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_workout_templates_user ON workout_templates (user_id);

-- =====================================================
-- template_items — exercises prescribed in a template
-- =====================================================
CREATE TABLE template_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,  -- denormalized for RLS
    template_id UUID NOT NULL REFERENCES workout_templates(id) ON DELETE CASCADE,
    exercise_key TEXT NOT NULL REFERENCES exercises(key),
    position INTEGER NOT NULL DEFAULT 0,
    target_reps INTEGER,
    target_duration_seconds NUMERIC(8, 2),
    target_load_kg NUMERIC(6, 2),
    target_distance_m NUMERIC(8, 2),
    rest_seconds NUMERIC(8, 2),
    variant TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_template_items_template ON template_items (template_id, position);

-- =====================================================
-- workout_sessions — a logged session
-- =====================================================
CREATE TABLE workout_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    session_date DATE NOT NULL,
    template_id UUID REFERENCES workout_templates(id) ON DELETE SET NULL,
    type workout_type NOT NULL DEFAULT 'circuit',
    total_minutes NUMERIC(6, 1),
    how_felt TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_workout_sessions_user_date ON workout_sessions (user_id, session_date DESC);

-- =====================================================
-- exercise_sets — the ACTUAL performance (heart of progress)
-- =====================================================
CREATE TABLE exercise_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,  -- denormalized for RLS
    session_id UUID NOT NULL REFERENCES workout_sessions(id) ON DELETE CASCADE,
    exercise_key TEXT NOT NULL REFERENCES exercises(key),

    round_number INTEGER,
    set_index INTEGER,
    variant TEXT,                                -- front|back|left|right|forward|backward

    -- Dimension columns: an exercise fills only the ones it uses.
    reps INTEGER,
    duration_seconds NUMERIC(8, 2),
    load_kg NUMERIC(6, 2),
    distance_m NUMERIC(8, 2),
    time_seconds NUMERIC(8, 3),                  -- a measured result (sprint time)

    rpe INTEGER CHECK (rpe IS NULL OR rpe BETWEEN 1 AND 10),
    started_at TIMESTAMPTZ,                       -- per-set wall-clock -> rest/density analysis
    ended_at TIMESTAMPTZ,
    notes TEXT,
    extra JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_exercise_sets_session ON exercise_sets (session_id, round_number, set_index);
CREATE INDEX idx_exercise_sets_user_exercise ON exercise_sets (user_id, exercise_key);

COMMENT ON TABLE exercise_sets IS 'Per-exercise sets actually performed; wide-nullable dims + started/ended for rest/density (like splits)';

-- =====================================================
-- Triggers — updated_at (function from initial_schema)
-- =====================================================
CREATE TRIGGER update_exercises_updated_at BEFORE UPDATE ON exercises
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_workout_templates_updated_at BEFORE UPDATE ON workout_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_workout_sessions_updated_at BEFORE UPDATE ON workout_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- Row Level Security
-- =====================================================
ALTER TABLE exercises ENABLE ROW LEVEL SECURITY;
CREATE POLICY "exercises readable by all" ON exercises FOR SELECT USING (TRUE);

-- Per-user tables: strict, no anon escape.
ALTER TABLE workout_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE template_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE workout_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_sets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own workout_templates select" ON workout_templates FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "own workout_templates insert" ON workout_templates FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "own workout_templates update" ON workout_templates FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY "own workout_templates delete" ON workout_templates FOR DELETE USING (user_id = auth.uid());

CREATE POLICY "own template_items select" ON template_items FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "own template_items insert" ON template_items FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "own template_items update" ON template_items FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY "own template_items delete" ON template_items FOR DELETE USING (user_id = auth.uid());

CREATE POLICY "own workout_sessions select" ON workout_sessions FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "own workout_sessions insert" ON workout_sessions FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "own workout_sessions update" ON workout_sessions FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY "own workout_sessions delete" ON workout_sessions FOR DELETE USING (user_id = auth.uid());

CREATE POLICY "own exercise_sets select" ON exercise_sets FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "own exercise_sets insert" ON exercise_sets FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "own exercise_sets update" ON exercise_sets FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY "own exercise_sets delete" ON exercise_sets FOR DELETE USING (user_id = auth.uid());
