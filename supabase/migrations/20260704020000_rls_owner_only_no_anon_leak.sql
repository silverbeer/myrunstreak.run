-- Security fix: remove the `OR auth.uid() IS NULL` escape hatch from the RLS
-- policies added in 20260704010000_fix_security_advisor.sql.
--
-- The problem: `auth.uid()` is NULL for the anon (unauthenticated) role, so
-- `USING (user_id = auth.uid() OR auth.uid() IS NULL)` evaluates to TRUE for any
-- anonymous caller — RLS then lets anon read the ENTIRE users table (every
-- email) and all sync_history. On Supabase-hosted prod the anon role holds the
-- default SELECT grant on public tables, and the anon key is public (it ships in
-- the frontend bundle for supabase.auth.*), so this exposed all user emails to
-- anyone. (Local dev didn't show it only because anon lacks the table grant.)
--
-- The clause was never needed: the backend uses the service-role key, which
-- BYPASSES RLS entirely — it doesn't consult these policies at all. Removing the
-- clause makes the policies genuinely owner-only. Authenticated users already
-- resolve to their own row (auth.uid() = their uid); anon now matches nothing.
--
-- IDEMPOTENT: DROP IF EXISTS + CREATE. Safe to re-run; a no-op once applied.

-- =====================================================
-- users — owner-only
-- =====================================================

DROP POLICY IF EXISTS "Users can view their own profile" ON users;
CREATE POLICY "Users can view their own profile"
    ON users FOR SELECT
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Users can update their own profile" ON users;
CREATE POLICY "Users can update their own profile"
    ON users FOR UPDATE
    USING (user_id = auth.uid());

-- =====================================================
-- sync_history — owner-only (via the user's sources)
-- =====================================================

DROP POLICY IF EXISTS "Users can view their own sync history" ON sync_history;
CREATE POLICY "Users can view their own sync history"
    ON sync_history FOR SELECT
    USING (
        source_id IN (
            SELECT id FROM user_sources WHERE user_id = auth.uid()
        )
    );
