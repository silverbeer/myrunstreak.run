#!/usr/bin/env bash
# Restore production Supabase data to the local Supabase instance.
#
# Workflow:
#   1. Reset local DB (applies all migrations from supabase/migrations/)
#   2. Dump production public-schema data via pg_dump
#   3. Load dump into local DB via psql
#
# Schema comes from migrations, not the dump. This keeps local schema aligned
# with the migration history and works even when prod hasn't received a new
# migration yet.
#
# Requirements:
#   - supabase CLI (for local dev)
#   - pg_dump, psql (PostgreSQL client tools)
#   - PROD_DATABASE_URL from one of: shell env, .env, or .env.restore
#
# WARNING: Downloads production data (may contain PII) to your laptop. Treat
# the dump file as sensitive. The script deletes it on exit but check your
# backups/trash.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DUMP_FILE="$(mktemp -t myrunstreak_prod_dump.XXXXXX.sql)"
trap 'rm -f "$DUMP_FILE"' EXIT

# Local Supabase default (from supabase/config.toml: [db] port = 54322)
LOCAL_DB_URL="${LOCAL_DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}"

# Load PROD_DATABASE_URL from .env or .env.restore if not already set.
# Both files are gitignored. .env is the main app env file; .env.restore is a
# separate file if you prefer to keep DB dumps creds isolated from app config.
# Priority: shell env > .env.restore > .env
for env_file in .env.restore .env; do
    if [[ -z "${PROD_DATABASE_URL:-}" && -f "$env_file" ]]; then
        # Grep only the var we need to avoid leaking other secrets into shell
        line=$(grep -E '^[[:space:]]*PROD_DATABASE_URL[[:space:]]*=' "$env_file" || true)
        if [[ -n "$line" ]]; then
            # Strip leading/trailing whitespace, leading "export ", surrounding quotes
            value="${line#*=}"
            value="${value%\"}"; value="${value#\"}"
            value="${value%\'}"; value="${value#\'}"
            export PROD_DATABASE_URL="$value"
            echo "Loaded PROD_DATABASE_URL from $env_file"
        fi
    fi
done

if [[ -z "${PROD_DATABASE_URL:-}" ]]; then
    cat >&2 <<EOF
ERROR: PROD_DATABASE_URL not set.

Get the prod connection string from Supabase dashboard:
  Project → Settings → Database → Connection string → URI

Then either export it:
  export PROD_DATABASE_URL='postgresql://postgres.xxxxx:PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres'

Or add to .env (or .env.restore):
  PROD_DATABASE_URL='postgresql://...'
EOF
    exit 1
fi

# Check required tools
for cmd in supabase pg_dump psql; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: '$cmd' not found on PATH" >&2
        exit 1
    fi
done

# Confirm destructive action
echo "This will:"
echo "  1. RESET the local Supabase DB (all local data destroyed)"
echo "  2. Apply all migrations from supabase/migrations/"
echo "  3. Dump public-schema data from PROD"
echo "  4. Load prod data into local DB"
echo ""
echo "Local DB: $LOCAL_DB_URL"
echo "Prod DB:  ${PROD_DATABASE_URL%%@*}@<redacted>"
echo ""
read -r -p "Continue? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Aborted."
    exit 0
fi

# Step 1: reset local DB (applies migrations)
echo ""
echo "==> Resetting local Supabase DB..."
supabase db reset

# Step 2: dump prod data
echo ""
echo "==> Dumping prod public-schema data..."
# --data-only: schema already applied via migrations
# --disable-triggers: avoid trigger side effects on reload
# --schema=public: exclude auth, storage, supabase internals
# --no-owner --no-acl: strip ownership/grants (different between envs)
pg_dump \
    --data-only \
    --disable-triggers \
    --schema=public \
    --no-owner \
    --no-acl \
    --file="$DUMP_FILE" \
    "$PROD_DATABASE_URL"

DUMP_SIZE=$(wc -c < "$DUMP_FILE" | tr -d ' ')
echo "    Dumped $DUMP_SIZE bytes"

# Step 3: load into local
echo ""
echo "==> Loading dump into local DB..."
psql \
    --single-transaction \
    --set ON_ERROR_STOP=on \
    --quiet \
    --dbname="$LOCAL_DB_URL" \
    --file="$DUMP_FILE"

echo ""
echo "==> Done."
echo ""
echo "Row counts in local:"
psql --dbname="$LOCAL_DB_URL" --quiet --no-align --tuples-only <<'SQL'
SELECT 'users: ' || COUNT(*) FROM users
UNION ALL SELECT 'user_sources: ' || COUNT(*) FROM user_sources
UNION ALL SELECT 'runs: ' || COUNT(*) FROM runs
UNION ALL SELECT 'splits: ' || COUNT(*) FROM splits
UNION ALL SELECT 'goals: ' || COUNT(*) FROM goals;
SQL
