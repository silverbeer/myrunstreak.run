-- =====================================================
-- Athlete profile (SB-219, SB-189 Phase 1). A 1:1 companion to `athletes`
-- holding the rich profile. Kept separate so the lean `athletes` identity row
-- (loaded in roster/coach-link hot paths) stays small, and so a minor's PII +
-- the coach-private `coaching_notes` are isolated for RLS/redaction.
--
-- Field ownership is enforced in the backend (service-role bypasses RLS): the
-- coach owns everything; the linked athlete may edit only a subset and never
-- sees `coaching_notes`. These policies are the second line of defence for
-- direct anon-key access, mirroring the `athletes` policies.
-- =====================================================
CREATE TABLE athlete_profiles (
    athlete_id UUID PRIMARY KEY REFERENCES athletes(id) ON DELETE CASCADE,
    -- sport
    sport TEXT,
    position TEXT,
    team TEXT,
    dominant_side TEXT CHECK (dominant_side IN ('left', 'right', 'both')),
    jersey_number TEXT,
    -- physical
    height_cm NUMERIC,
    weight_kg NUMERIC,
    date_of_birth DATE,
    sex TEXT CHECK (sex IN ('male', 'female', 'other')),
    -- athlete-owned free text
    bio TEXT,
    personal_goals TEXT,
    -- contact / guardian (athlete is typically a minor)
    athlete_email TEXT,
    athlete_phone TEXT,
    guardian_name TEXT,
    guardian_email TEXT,
    guardian_phone TEXT,
    -- coach-private (never returned to the linked athlete)
    coaching_notes TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID REFERENCES users(user_id) ON DELETE SET NULL
);

COMMENT ON COLUMN athlete_profiles.coaching_notes IS
    'Coach-private; redacted from the linked-athlete read path (SB-219)';

-- True if the caller is the athlete (linked user) or an active coach of them.
-- Reused by the profile RLS below.
CREATE FUNCTION can_access_athlete_row(aid UUID) RETURNS BOOLEAN
LANGUAGE sql STABLE AS $$
    SELECT EXISTS (SELECT 1 FROM athletes WHERE id = aid AND linked_user_id = auth.uid())
        OR EXISTS (
            SELECT 1 FROM coach_athletes
            WHERE athlete_id = aid AND coach_id = auth.uid() AND status = 'active'
        );
$$;

ALTER TABLE athlete_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "athlete_profiles select" ON athlete_profiles FOR SELECT
    USING (can_access_athlete_row(athlete_id));
CREATE POLICY "athlete_profiles insert" ON athlete_profiles FOR INSERT
    WITH CHECK (can_access_athlete_row(athlete_id));
CREATE POLICY "athlete_profiles update" ON athlete_profiles FOR UPDATE
    USING (can_access_athlete_row(athlete_id));
