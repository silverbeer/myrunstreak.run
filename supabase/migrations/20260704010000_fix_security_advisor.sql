-- Fix Supabase security advisor errors.
--
-- Issues addressed:
--   1. RLS disabled on `public.users` and `public.sync_history`.
--   2. `daily_summary` and `monthly_summary` views run as SECURITY DEFINER
--      (Postgres default), so they bypass the querying user's RLS on `runs`.
--
-- Service-role keys (used by the backend) bypass RLS, so backend sync continues
-- to work. Anon/authenticated keys will be subject to the policies below.
--
-- Note: `runs`, `splits`, `user_sources`, etc. already have RLS enabled by the
-- initial schema (20251119133437). This migration only closes the gap on
-- `users` + `sync_history` and hardens the two summary views. View column sets
-- match the current definitions in 20260301000001_increase_distance_precision.
--
-- IDEMPOTENT: prod already has this state applied manually via the Supabase
-- dashboard (RLS + these exact policies + security_invoker views), but it was
-- never captured as a migration. This migration codifies that drift so fresh
-- databases (CI shadow, local dev, new environments) reproduce it. The
-- ENABLE/DROP-IF-EXISTS/CREATE pattern is a no-op on prod and a real fix
-- everywhere else.

-- =====================================================
-- 1. ENABLE RLS ON users
-- =====================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own profile" ON users;
CREATE POLICY "Users can view their own profile"
    ON users FOR SELECT
    USING (user_id = auth.uid() OR auth.uid() IS NULL);

DROP POLICY IF EXISTS "Users can update their own profile" ON users;
CREATE POLICY "Users can update their own profile"
    ON users FOR UPDATE
    USING (user_id = auth.uid() OR auth.uid() IS NULL);

-- =====================================================
-- 2. ENABLE RLS ON sync_history
-- =====================================================

ALTER TABLE sync_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own sync history" ON sync_history;
CREATE POLICY "Users can view their own sync history"
    ON sync_history FOR SELECT
    USING (
        source_id IN (
            SELECT id FROM user_sources
            WHERE user_id = auth.uid() OR auth.uid() IS NULL
        )
    );

-- =====================================================
-- 3. RECREATE VIEWS WITH security_invoker
-- =====================================================
-- Postgres 15+ supports security_invoker on views. With it enabled the view
-- executes with the querying user's permissions and RLS policies on `runs`,
-- which is the correct behavior for analytics views over user-scoped data.
-- Column sets below mirror 20260301000001 (increase_distance_precision).

DROP VIEW IF EXISTS daily_summary;
DROP VIEW IF EXISTS monthly_summary;

CREATE VIEW daily_summary
    WITH (security_invoker = true)
AS
SELECT
    user_id,
    start_date,
    COUNT(*) AS run_count,
    SUM(distance_km) AS total_km,
    AVG(distance_km) AS avg_km,
    AVG(average_pace_min_per_km) AS avg_pace,
    MIN(start_date_time_local) AS first_run,
    MAX(start_date_time_local) AS last_run
FROM runs
GROUP BY user_id, start_date
ORDER BY user_id, start_date DESC;

CREATE VIEW monthly_summary
    WITH (security_invoker = true)
AS
SELECT
    user_id,
    start_year,
    start_month,
    TO_DATE(start_year || '-' || start_month || '-01', 'YYYY-MM-DD') AS month_start,
    COUNT(*) AS run_count,
    SUM(distance_km) AS total_km,
    AVG(distance_km) AS avg_km,
    MAX(distance_km) AS longest_run_km,
    AVG(average_pace_min_per_km) AS avg_pace
FROM runs
GROUP BY user_id, start_year, start_month
ORDER BY user_id, start_year DESC, start_month DESC;

COMMENT ON VIEW daily_summary IS 'Daily statistics per user (security_invoker)';
COMMENT ON VIEW monthly_summary IS 'Monthly statistics per user (security_invoker)';
