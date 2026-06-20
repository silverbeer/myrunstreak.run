-- =====================================================
-- Invite-only onboarding (SB-188): an admin issues an invite (token + email,
-- with an expiry); the invitee self-signs-up with the token and sets their own
-- password via Supabase Auth. This table is the issue/redeem ledger.
--
-- The backend connects with the service-role key (bypasses RLS) and scopes
-- every query in code; RLS here is the second line of defence for direct
-- anon-key access. Issue + redeem are server-side (service-role) operations,
-- so the only end-user-facing policy is "see the invites you issued".
-- =====================================================
CREATE TABLE invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token TEXT NOT NULL UNIQUE,                 -- opaque, URL-safe; what the invitee redeems
    email TEXT NOT NULL,                        -- who it was issued to
    created_by UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    redeemed_at TIMESTAMPTZ,                    -- NULL until redeemed
    redeemed_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_invites_token ON invites (token);
CREATE INDEX idx_invites_created_by ON invites (created_by);

COMMENT ON TABLE invites IS 'Invite-only onboarding ledger (SB-188): admin issues, invitee redeems at signup';
COMMENT ON COLUMN invites.token IS 'Opaque URL-safe secret the invitee presents to sign up';
COMMENT ON COLUMN invites.redeemed_at IS 'Set when the invite is consumed; a non-NULL value means it can no longer be used';

-- RLS: strict. Issue/redeem run server-side via the service-role key (which
-- bypasses these). The only anon-key-reachable action is reading invites you
-- issued — never another admin's, never by token (redeem is server-side only).
ALTER TABLE invites ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own invites select"
    ON invites FOR SELECT
    USING (created_by = auth.uid());
