-- =====================================================
-- Add warm-up and cool-down to the exercise catalog.
-- They bracket every session (first + last item on the card) and matter as
-- much as the work — coaches track that the athlete actually did them.
-- Modeled as duration-based mobility movements so they round-trip like any
-- other exercise. Idempotent: safe to re-run.
-- =====================================================
INSERT INTO exercises (key, display_name, category, measures, is_benchmark) VALUES
    ('warmup',   'Warm-up',   'mobility', ARRAY['duration_s'], FALSE),
    ('cooldown', 'Cool-down', 'mobility', ARRAY['duration_s'], FALSE)
ON CONFLICT (key) DO NOTHING;
