-- =====================================================
-- Runner role + test-account flag (SB-367).
--
-- `user_roles` is already many-to-many (PK (user_id, role)), so a user can hold
-- admin + coach + runner at once — that needed no change. What was missing:
--
--   1. The `user_role` enum had no 'runner', so "this user runs" (and its
--      converse, "this coach does not run") could not be expressed. Running was
--      implicit in being a user, which stops working once coaches exist who
--      only coach.
--   2. Nothing marked an account as a test account, so a future follow / social
--      feature would surface the seeded test users alongside real ones.
--
-- Athlete-ness is deliberately NOT a role: it is derived from
-- `athletes.linked_user_id`. A role row would be a second copy of the same fact
-- and would drift when an athlete is linked or unlinked, and a *managed*
-- athlete has no user row to hold one at all. An athlete does not need a coach
-- — `coach_athletes` is a separate table and the derived check never consults
-- it. `GET /me/roles` synthesizes "athlete" so the API still returns a uniform
-- role list.
--
-- NOTE: `ALTER TYPE ... ADD VALUE` cannot be *used* in the transaction that
-- adds it, and Supabase wraps each migration in one. Nothing here inserts a
-- 'runner' row, so this is safe as a single migration — but any future
-- migration that grants the runner role must live in its own file.
-- =====================================================

ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'runner';

-- ---- test-account flag ------------------------------

ALTER TABLE users ADD COLUMN is_test_account BOOLEAN NOT NULL DEFAULT FALSE;
COMMENT ON COLUMN users.is_test_account IS
    'Seeded test login (SB-367); exclude from social/discovery surfaces';

ALTER TABLE athletes ADD COLUMN is_test_account BOOLEAN NOT NULL DEFAULT FALSE;
COMMENT ON COLUMN athletes.is_test_account IS
    'Seeded test athlete (SB-367); exclude from social/discovery surfaces';

-- Partial indexes: the flagged set is tiny and the interesting query is always
-- "which are the test rows", never "which are the real ones".
CREATE INDEX idx_users_test_account ON users (user_id) WHERE is_test_account;
CREATE INDEX idx_athletes_test_account ON athletes (id) WHERE is_test_account;
