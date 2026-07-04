-- SB-224: give the service_role DML on public tables so the Supabase REST API
-- (PostgREST) works in every environment.
--
-- Why this is needed: the FastAPI backend connects to Postgres directly as the
-- superuser, so nothing ever exercised the service_role's *table* grants
-- locally. The REST tooling (scripts/backup_database.py, restore_database.py,
-- seed_local_users.py) connects through PostgREST as service_role, which needs
-- table-level SELECT/INSERT/UPDATE/DELETE. Locally these were never granted
-- (fresh `supabase db reset` left service_role with only TRUNCATE/REFERENCES/
-- TRIGGER), so REST calls failed with "permission denied for table".
--
-- On Supabase-hosted prod service_role already holds these privileges, so this
-- migration is a harmless re-grant there. service_role also bypasses RLS, so no
-- RLS policy changes are implied. Sequences are covered for completeness even
-- though current tables use UUID primary keys.

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- Future tables/sequences created in this schema inherit the same grants.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO service_role;
