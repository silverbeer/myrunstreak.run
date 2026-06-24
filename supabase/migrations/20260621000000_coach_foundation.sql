-- =====================================================
-- Coach platform foundation (SB-195): identity + relationships.
--
--   user_roles      who is an admin / coach (retires the ADMIN_USER_IDS hack)
--   athletes        a trackable person — managed (no login) or linked to a user
--   coach_athletes  the coach<->athlete relationship over time (active|ended)
--
-- Data is owned by the ATHLETE (later: workouts reference athlete_id), so a new
-- coach sees the full history and reassigning coaches re-homes nothing. Access
-- is granted by an ACTIVE coach link (or being the linked user, or admin).
--
-- The backend uses the service-role key (bypasses RLS) and enforces access in
-- code (can_access_athlete). RLS here is the second line of defence for direct
-- anon-key access.
-- =====================================================

CREATE TYPE user_role AS ENUM ('admin', 'coach');
CREATE TYPE coach_athlete_status AS ENUM ('active', 'ended');

-- ---- tables -----------------------------------------

-- user_roles — replaces the ADMIN_USER_IDS env allowlist
CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role user_role NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, role)
);
COMMENT ON TABLE user_roles IS 'Per-user platform roles (SB-195); admin/coach grants';

-- athletes — the training subject (managed or linked to a login)
CREATE TABLE athletes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name TEXT NOT NULL,
    birth_year INT,                                   -- minor-aware; age-norms later
    linked_user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,  -- self/parent login (future)
    created_by UUID NOT NULL REFERENCES users(user_id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_athletes_linked_user ON athletes (linked_user_id);
CREATE INDEX idx_athletes_created_by ON athletes (created_by);
COMMENT ON TABLE athletes IS 'A trackable athlete (SB-195); managed (no login) or linked to a user';
COMMENT ON COLUMN athletes.linked_user_id IS 'If set, that user IS this athlete (self/parent access)';

-- coach_athletes — the relationship over time
CREATE TABLE coach_athletes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    coach_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    status coach_athlete_status NOT NULL DEFAULT 'active',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- At most one active link per (coach, athlete); re-coaching after an end is fine.
CREATE UNIQUE INDEX idx_coach_athletes_active
    ON coach_athletes (coach_id, athlete_id)
    WHERE status = 'active';
CREATE INDEX idx_coach_athletes_coach ON coach_athletes (coach_id, status);
CREATE INDEX idx_coach_athletes_athlete ON coach_athletes (athlete_id, status);
COMMENT ON TABLE coach_athletes IS 'Coach<->athlete relationship history (SB-195); active row = current coach';

-- ---- RLS (after all tables exist, since policies cross-reference) ----

ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own roles select" ON user_roles FOR SELECT USING (user_id = auth.uid());

ALTER TABLE athletes ENABLE ROW LEVEL SECURITY;
-- See/edit an athlete if you ARE them, or you actively coach them.
CREATE POLICY "athletes select" ON athletes FOR SELECT
    USING (
        linked_user_id = auth.uid()
        OR id IN (
            SELECT athlete_id FROM coach_athletes
            WHERE coach_id = auth.uid() AND status = 'active'
        )
    );
CREATE POLICY "athletes insert" ON athletes FOR INSERT
    WITH CHECK (created_by = auth.uid());
CREATE POLICY "athletes update" ON athletes FOR UPDATE
    USING (
        linked_user_id = auth.uid()
        OR id IN (
            SELECT athlete_id FROM coach_athletes
            WHERE coach_id = auth.uid() AND status = 'active'
        )
    );

ALTER TABLE coach_athletes ENABLE ROW LEVEL SECURITY;
-- A coach manages + sees their own links; an athlete sees who coaches them.
CREATE POLICY "coach_athletes select" ON coach_athletes FOR SELECT
    USING (
        coach_id = auth.uid()
        OR athlete_id IN (SELECT id FROM athletes WHERE linked_user_id = auth.uid())
    );
CREATE POLICY "coach_athletes insert" ON coach_athletes FOR INSERT
    WITH CHECK (coach_id = auth.uid());
CREATE POLICY "coach_athletes update" ON coach_athletes FOR UPDATE
    USING (coach_id = auth.uid());

-- ---- seed: owner is admin + coach (usable immediately; keeps invites working) ----
-- Guarded: only grants when that user actually exists (prod), so fresh/local/CI
-- databases without the owner row apply this migration cleanly instead of
-- tripping the user_roles -> users foreign key.
INSERT INTO user_roles (user_id, role)
SELECT '16eb502d-7fc0-4fce-9107-9931df747e28'::uuid, role
FROM (VALUES ('admin'::user_role), ('coach'::user_role)) AS v(role)
WHERE EXISTS (
    SELECT 1 FROM users WHERE user_id = '16eb502d-7fc0-4fce-9107-9931df747e28'
)
ON CONFLICT DO NOTHING;
