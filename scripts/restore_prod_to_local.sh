#!/usr/bin/env bash
# Restore production STK run-data into the LOCAL Supabase — over the REST API.
#
# Why REST and not pg_dump (SB-224):
#   The prod direct DB host (db.<ref>.supabase.co) is IPv6-only ("No route to
#   host" on an IPv4 network) and the session pooler rejects the tenant here.
#   The Supabase REST API is plain HTTPS, so it works fine on IPv4. We dump prod
#   over REST with the service-role key, then load it into local over REST.
#
# Flow:
#   1. Read prod creds (op) and back up prod run-data -> ~/backups/stk/*.json.gz
#   2. `jt supabase sync-users stk` — recreate silverbeer locally w/ prod uid
#   3. Restore the backup into local (clears + reloads run-data tables)
#   4. `seed_local_users.py` — (re)create the coach/athlete test data
#
# EXCLUDED from the copy: auth users (step 2 owns them), OAuth tokens (scrubbed
# from the dump), invites, and the coach/athlete domain (step 4 owns it).
#
# Run this yourself — it uses `op` (1Password), which needs biometric auth and
# will not work in a non-interactive agent shell.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BACKUP_DIR="${STK_BACKUP_DIR:-$HOME/backups/stk}"

# --- Prod credentials -------------------------------------------------------
# URL is public; service key comes from 1Password. Override PROD_* to skip op.
PROD_URL="${STK_PROD_SUPABASE_URL:-https://dnwllbukmvdddwhlsmqb.supabase.co}"
PROD_KEY="${STK_PROD_SERVICE_KEY:-}"

if [[ -z "$PROD_KEY" ]]; then
    if ! command -v op >/dev/null 2>&1; then
        echo "ERROR: 'op' (1Password CLI) not found and STK_PROD_SERVICE_KEY unset." >&2
        exit 1
    fi
    echo "==> Reading prod service key from 1Password..."
    PROD_KEY="$(op read 'op://Personal/stk-prod/service_role_key')"
fi

# --- Confirm destructive action --------------------------------------------
echo "This will OVERWRITE local run-data (runs, splits, goals, metrics) with prod's."
echo "  Prod:  $PROD_URL"
echo "  Local: (discovered via 'supabase status')"
echo "  Backup dir: $BACKUP_DIR"
echo ""
read -r -p "Continue? [y/N] " confirm
[[ "$confirm" == "y" || "$confirm" == "Y" ]] || { echo "Aborted."; exit 0; }

# --- Step 1: back up prod over REST ----------------------------------------
echo ""
echo "==> Step 1/4: backing up prod run-data over REST..."
SUPABASE_URL="$PROD_URL" SUPABASE_SERVICE_KEY="$PROD_KEY" \
    uv run --project backend python scripts/backup_database.py --backup-dir "$BACKUP_DIR"

# --- Discover local creds ---------------------------------------------------
echo ""
echo "==> Discovering local Supabase creds..."
eval "$(supabase status -o env | sed 's/^/export SB_/')"
LOCAL_URL="${SB_API_URL:-http://127.0.0.1:54321}"
LOCAL_KEY="${SB_SERVICE_ROLE_KEY:?supabase status did not return SERVICE_ROLE_KEY — is the stack running?}"

# --- Step 2: sync auth users (silverbeer gets prod uid) ---------------------
echo ""
echo "==> Step 2/4: syncing auth users (jt supabase sync-users stk)..."
if command -v jt >/dev/null 2>&1; then
    jt supabase sync-users stk
else
    echo "WARNING: 'jt' not found — skipping sync-users. Run-data for users not"
    echo "         present locally will be dropped on restore." >&2
fi

# --- Step 3: restore into local over REST -----------------------------------
echo ""
echo "==> Step 3/4: restoring backup into local..."
SUPABASE_URL="$LOCAL_URL" SUPABASE_SERVICE_KEY="$LOCAL_KEY" \
    uv run --project backend python scripts/restore_database.py --latest --backup-dir "$BACKUP_DIR"

# --- Step 4: seed coach/athlete test data -----------------------------------
echo ""
echo "==> Step 4/4: seeding local coach/athlete test users..."
SUPABASE_URL="$LOCAL_URL" SUPABASE_SERVICE_ROLE_KEY="$LOCAL_KEY" \
    uv run --project backend python scripts/seed_local_users.py

echo ""
echo "==> Done. Log into the app as silverbeer.io@gmail.com to see real data;"
echo "    coach@test.local / coach123 still has the seeded test athletes."
