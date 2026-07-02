-- =====================================================
-- Athlete onboarding (SB-212, SB-189 P4-2): an invite can be tied to a managed
-- athlete. When such an invite is redeemed, the new user is linked to that
-- athlete (athletes.linked_user_id = new uid), so the athlete becomes a
-- logged-in user #2 who sees their own data via the existing linked_user_id
-- RLS. Nothing set linked_user_id before this.
-- =====================================================
ALTER TABLE invites ADD COLUMN athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE;

COMMENT ON COLUMN invites.athlete_id IS
    'If set, redeeming links the new user to this athlete (athletes.linked_user_id) — SB-212 P4-2';
