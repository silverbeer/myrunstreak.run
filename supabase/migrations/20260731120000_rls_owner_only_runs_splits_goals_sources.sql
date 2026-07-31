-- Security fix (SB-453): remove the `OR auth.uid() IS NULL` escape hatch from
-- every remaining RLS policy — runs, splits, goals and user_sources.
--
-- Same defect SB-227 established the guardrail for and 20260704020000 fixed for
-- users/sync_history: `auth.uid()` is NULL for the anon role, so
-- `USING (user_id = auth.uid() OR auth.uid() IS NULL)` is TRUE for every
-- unauthenticated caller and the policy degrades to "allow everyone".
--
-- Confirmed exploitable on prod 2026-07-31, unauthenticated, using only the
-- public anon key that ships in the frontend bundle:
--
--     runs          4,785 rows
--     splits       20,677 rows
--     goals             5 rows
--     user_sources      1 row  — INCLUDING access_token, refresh_token and
--                                access_token_secret
--
-- The user_sources exposure is the severe one: those are live SmashRun OAuth
-- credentials, so this was account takeover, not just a data leak. Tokens are
-- being rotated separately; this migration closes the hole.
--
-- Local dev never showed it because the anon role there lacks the table SELECT
-- grant, so RLS was never reached. Do not treat a clean local as evidence.
--
-- The clause was never needed: the backend uses the service-role key, which
-- BYPASSES RLS entirely. Authenticated browser sessions resolve auth.uid() to
-- the caller, so they keep seeing exactly their own rows. Anon now matches
-- nothing.
--
-- IDEMPOTENT: DROP IF EXISTS + CREATE. Safe to re-run; a no-op once applied.

-- =====================================================
-- runs — owner-only
-- =====================================================

DROP POLICY IF EXISTS "Users can view their own runs" ON runs;
CREATE POLICY "Users can view their own runs"
    ON runs FOR SELECT
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can insert their own runs" ON runs;
CREATE POLICY "Users can insert their own runs"
    ON runs FOR INSERT
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can update their own runs" ON runs;
CREATE POLICY "Users can update their own runs"
    ON runs FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());  -- explicit: post-update row stays owned

-- =====================================================
-- splits — owner-only, scoped through the parent run
-- =====================================================

DROP POLICY IF EXISTS "Users can view their own splits" ON splits;
CREATE POLICY "Users can view their own splits"
    ON splits FOR SELECT
    USING (run_id IN (SELECT id FROM runs WHERE user_id = auth.uid()));

-- =====================================================
-- goals — owner-only
-- =====================================================

DROP POLICY IF EXISTS "Users can view their own goals" ON goals;
CREATE POLICY "Users can view their own goals"
    ON goals FOR SELECT
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can insert their own goals" ON goals;
CREATE POLICY "Users can insert their own goals"
    ON goals FOR INSERT
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can update their own goals" ON goals;
CREATE POLICY "Users can update their own goals"
    ON goals FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- =====================================================
-- user_sources — owner-only. Holds OAuth tokens; nothing anonymous reads this.
-- =====================================================

DROP POLICY IF EXISTS "Users can view their own user_sources" ON user_sources;
CREATE POLICY "Users can view their own user_sources"
    ON user_sources FOR SELECT
    USING (user_id = auth.uid());
