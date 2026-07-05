-- =====================================================
-- Exercise catalog: canonical library + private/public + metadata (SB-228 D1)
-- =====================================================
-- Turns the read-only global `exercises` catalog into a shared, deduplicated
-- library that coaches contribute to:
--   * a canonical PUBLIC library (owner_id IS NULL, visibility='public') — the
--     existing seeded rows become it automatically (visibility defaults public).
--   * coach-owned PRIVATE exercises (owner_id set, visibility='private'), which
--     can be promoted to public at any time.
--
-- Design decision: `key` stays the PRIMARY KEY (globally unique slug). The
-- backend generates a unique slug per new exercise, so no PK change and no FK
-- repoint on template_items / exercise_sets (both reference exercises(key) and
-- may already hold athlete data). All new capability is additive columns.
--
-- Dedup is soft: search-first UX + aliases folding synonyms + a publish-time
-- near-duplicate warning (enforced in the app, not by a unique-on-name
-- constraint — real variants like push-up vs incline push-up must coexist).
--
-- RLS follows the project guardrail: owner-or-public, NO `auth.uid() IS NULL`
-- escape. The backend uses the service-role key (bypasses RLS) to seed the
-- canonical library and to enforce ownership in code.
-- =====================================================

-- ===== New enums (classification facets) =====
CREATE TYPE exercise_visibility AS ENUM ('private', 'public');
CREATE TYPE movement_pattern AS ENUM (
    'squat', 'hinge', 'lunge', 'push', 'pull', 'carry',
    'rotation', 'anti_rotation', 'jump', 'sprint', 'isometric', 'mobility', 'other'
);
CREATE TYPE laterality AS ENUM ('bilateral', 'unilateral');
CREATE TYPE difficulty AS ENUM ('beginner', 'intermediate', 'advanced');

-- ===== Additive columns on exercises =====
ALTER TABLE exercises
    ADD COLUMN owner_id     UUID REFERENCES users(user_id) ON DELETE CASCADE,   -- NULL = canonical library
    ADD COLUMN visibility   exercise_visibility NOT NULL DEFAULT 'public',
    ADD COLUMN created_by   UUID REFERENCES users(user_id) ON DELETE SET NULL,
    ADD COLUMN forked_from  TEXT REFERENCES exercises(key) ON DELETE SET NULL,  -- clone-and-customize
    ADD COLUMN aliases      TEXT[] NOT NULL DEFAULT '{}',                        -- synonyms → dedup + search
    ADD COLUMN movement_pattern movement_pattern,
    ADD COLUMN equipment    TEXT[] NOT NULL DEFAULT '{}',                        -- bodyweight,dumbbell,band,...
    ADD COLUMN body_region  TEXT[] NOT NULL DEFAULT '{}',                        -- upper,lower,core,full
    ADD COLUMN laterality   laterality,
    ADD COLUMN difficulty   difficulty,
    ADD COLUMN tags         TEXT[] NOT NULL DEFAULT '{}',                        -- freeform + sport
    ADD COLUMN media_url     TEXT,                                               -- demo video/gif
    ADD COLUMN thumbnail_url TEXT,
    ADD COLUMN cues         TEXT[] NOT NULL DEFAULT '{}',                        -- coaching cues
    ADD COLUMN instructions TEXT;

-- list_visible filters on these.
CREATE INDEX idx_exercises_owner ON exercises (owner_id);
CREATE INDEX idx_exercises_visibility ON exercises (visibility);
-- Alias membership for search/dedup.
CREATE INDEX idx_exercises_aliases ON exercises USING GIN (aliases);

-- ===== Enrich the seeded canonical rows (movement metadata + a few aliases) =====
UPDATE exercises SET movement_pattern='sprint',  body_region='{lower,full}', equipment='{none}',       laterality='bilateral',  difficulty='intermediate', aliases='{"40 yard dash","40-yard sprint","forty"}' WHERE key='40yd_dash';
UPDATE exercises SET movement_pattern='jump',    body_region='{lower}',      equipment='{none}',       laterality='bilateral',  difficulty='intermediate', aliases='{"vert","vertical leap"}'                    WHERE key='vertical_jump';
UPDATE exercises SET movement_pattern='jump',    body_region='{lower}',      equipment='{none}',       laterality='bilateral',  difficulty='intermediate', aliases='{"standing long jump"}'                       WHERE key='broad_jump';
UPDATE exercises SET movement_pattern='sprint',  body_region='{lower,full}', equipment='{cone}',       laterality='bilateral',  difficulty='intermediate', aliases='{"5-10-5","pro agility shuttle","short shuttle"}' WHERE key='pro_agility';
UPDATE exercises SET movement_pattern='push',    body_region='{upper,core}', equipment='{bodyweight}', laterality='bilateral',  difficulty='beginner',     aliases='{"press-up","press up"}', cues='{"Elbows ~45°","Straight line head to heels"}' WHERE key='pushups';
UPDATE exercises SET movement_pattern='isometric', body_region='{core}',     equipment='{bodyweight}', laterality='bilateral',  difficulty='beginner',     aliases='{"front plank"}', cues='{"Neutral spine","Brace the core"}' WHERE key='plank';
UPDATE exercises SET movement_pattern='jump',    body_region='{lower,full}', equipment='{jump_rope}',  laterality='bilateral',  difficulty='beginner',     aliases='{"skipping"}'                                 WHERE key='jump_rope';
UPDATE exercises SET movement_pattern='lunge',   body_region='{lower}',      equipment='{bodyweight}', laterality='unilateral', difficulty='beginner',     aliases='{"forward lunge","split squat"}'              WHERE key='lunge';
UPDATE exercises SET movement_pattern='jump',    body_region='{lower,full}', equipment='{none}',       laterality='bilateral',  difficulty='intermediate', aliases='{"frog leap"}'                                WHERE key='frog_jump';
UPDATE exercises SET movement_pattern='sprint',  body_region='{lower,full}', equipment='{none}',       laterality='bilateral',  difficulty='advanced',     aliases='{"hill run"}'                                 WHERE key='hill_sprint';
UPDATE exercises SET movement_pattern='isometric', body_region='{upper}',    equipment='{dumbbell}',   laterality='bilateral',  difficulty='intermediate', aliases='{"iso curl hold"}'                            WHERE key='bicep_hold';
UPDATE exercises SET movement_pattern='pull',    body_region='{upper}',      equipment='{dumbbell}',   laterality='bilateral',  difficulty='intermediate', aliases='{"row hold"}'                                 WHERE key='row_hold';
UPDATE exercises SET movement_pattern='mobility', body_region='{full}',      equipment='{none}',       laterality='bilateral',  difficulty='intermediate', aliases='{"bridge","wrestlers bridge"}'                WHERE key='back_bridge';

-- ===== RLS: owner-or-public (replaces the read-all policy) =====
DROP POLICY IF EXISTS "exercises readable by all" ON exercises;

CREATE POLICY "exercises select own or public" ON exercises FOR SELECT
    USING (visibility = 'public' OR owner_id = auth.uid());
CREATE POLICY "exercises insert own" ON exercises FOR INSERT
    WITH CHECK (owner_id = auth.uid());
CREATE POLICY "exercises update own" ON exercises FOR UPDATE
    USING (owner_id = auth.uid()) WITH CHECK (owner_id = auth.uid());
CREATE POLICY "exercises delete own" ON exercises FOR DELETE
    USING (owner_id = auth.uid());

COMMENT ON COLUMN exercises.owner_id IS 'NULL = canonical/public library; set = coach-owned';
COMMENT ON COLUMN exercises.visibility IS 'private (owner only) or public (shared library); promotable';
COMMENT ON COLUMN exercises.aliases IS 'Synonyms for search + dedup (fold variants onto one canonical row)';
