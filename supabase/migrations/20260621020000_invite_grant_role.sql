-- =====================================================
-- Coach onboarding (SB-204): an invite can carry a role to grant on redemption.
-- Invite a coach with grant_role = 'coach' → when they redeem, they're a coach
-- immediately (no separate admin step).
-- =====================================================
ALTER TABLE invites ADD COLUMN grant_role user_role;

COMMENT ON COLUMN invites.grant_role IS 'Role granted to the user on redemption (SB-204), e.g. coach';
