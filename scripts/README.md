# Scripts

Utility scripts for MyRunStreak.com development and testing.

## 🧪 Local Testing Scripts

### test_local_sync.py

**Test the Lambda sync function locally without AWS deployment.**

Simulates the Lambda function behavior using local file storage instead of AWS Secrets Manager and a local DuckDB database.

```bash
# First time: Will run OAuth flow
python scripts/test_local_sync.py

# Subsequent runs: Will sync new runs since last sync
python scripts/test_local_sync.py
```

**What it does:**
1. Runs OAuth flow (first time only)
2. Stores tokens locally in `./data/smashrun_tokens.json`
3. Fetches runs from SmashRun since last sync
4. Stores runs in local DuckDB at `./data/runs.duckdb`
5. Tracks sync state in `./data/sync_state.json`
6. Shows statistics in miles!

**First-time setup:**
- Make sure `.env` is configured with your SmashRun credentials
- Script will guide you through OAuth authorization
- Tokens are saved locally for future runs

### query_runs.py

**Query your local DuckDB database for running statistics.**

```bash
python scripts/query_runs.py
```

**Displays:**
- Overall statistics (total distance, average pace, etc.)
- Recent runs (last 10)
- Monthly summaries (last 12 months)
- Top 5 running streaks
- Personal records (longest run, fastest pace, etc.)

**All distances in miles!**

## 👥 Seed Scripts

Two mirror-image seeders. Each refuses to run against the environment the other one owns, so neither can be pointed at the wrong database by accident.

### seed_local_users.py

Local-only (refuses anything but `127.0.0.1`/`localhost`). Free to delete rows and repoint orphans. Seeds `admin@test.local`, `coach@test.local`, `a1@test.local`, `a2@test.local`.

```bash
eval "$(supabase status -o env | sed 's/^/export SB_/')"
SUPABASE_URL=$SB_API_URL SERVICE_KEY=$SB_SERVICE_ROLE_KEY \
  uv run python scripts/seed_local_users.py
```

### seed_prod_test_users.py

Prod-only (refuses localhost) and **non-destructive** — never deletes an auth user, never touches a row outside `@test.myrunstreak.run`, and refuses to repoint a conflicting `users` row rather than guessing. Re-running is a no-op.

| account | roles | notes |
|---|---|---|
| `coach@test.myrunstreak.run` | `coach` + `runner` | the working proof that multi-role works |
| `runner@test.myrunstreak.run` | `runner` | |
| `a1@test.myrunstreak.run` | `runner` | linked athlete "Test Athlete One", coached by `coach@` |

All rows get `is_test_account = TRUE` so a future follow/social feature can exclude them. `test.myrunstreak.run` has no MX record and accounts are created with `email_confirm: true`, so no mail ever reaches these addresses.

Requires migration `20260727000000_runner_role_and_test_accounts` — the script checks and fails with instructions if it hasn't been applied.

```bash
export SUPABASE_URL=https://<prod-ref>.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
export STK_TEST_PASSWORD=<shared password, 6+ chars — Supabase Auth's minimum>

# preview every write, touching nothing
uv run python scripts/seed_prod_test_users.py --dry-run

# actually seed
uv run python scripts/seed_prod_test_users.py --confirm-prod
```

To find the test accounts later: `SELECT * FROM users WHERE is_test_account;`

## 🔐 AWS Setup Scripts

### setup_smashrun_tokens.py

**Interactive script to complete OAuth flow and store tokens in AWS Secrets Manager.**

Use this when you're ready to deploy to AWS Lambda.

```bash
python scripts/setup_smashrun_tokens.py
```

**What it does:**
1. Guides you through OAuth authorization
2. Exchanges auth code for tokens
3. Stores tokens in AWS Secrets Manager
4. Secrets:
   - `myrunstreak/smashrun/tokens` - OAuth tokens
   - `myrunstreak/sync-state` - Sync state tracking

**Prerequisites:**
- AWS CLI configured with credentials
- IAM permissions for Secrets Manager
- SmashRun OAuth credentials in `.env`

## 📁 Local Data Files

When running local tests, data is stored in `./data/`:

```
./data/
├── smashrun_tokens.json     # OAuth tokens (local only)
├── sync_state.json          # Last sync date
└── runs.duckdb              # DuckDB database with runs
```

**⚠️ These files are in .gitignore - never committed!**

## 🔄 Typical Workflow

### 1. Local Testing

```bash
# Test OAuth and sync locally
python scripts/test_local_sync.py

# View your data
python scripts/query_runs.py

# Sync again to test incremental updates
python scripts/test_local_sync.py
```

### 2. Deploy to AWS

```bash
# Store tokens in AWS Secrets Manager
python scripts/setup_smashrun_tokens.py

# Deploy Lambda with Terraform
cd terraform/environments/dev
terraform apply
```

### 3. Monitor Production

```bash
# View Lambda logs
aws logs tail /aws/lambda/myrunstreak-sync --follow

# Check metrics
aws cloudwatch get-metric-statistics \
    --namespace MyRunStreak \
    --metric-name RunsSynced \
    --dimensions Name=service,Value=smashrun-sync \
    --start-time $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Sum
```

## 🐛 Troubleshooting

### OAuth Authorization Failed

**Error:** "Invalid authorization code"

**Fix:**
- Make sure you paste the code immediately (codes expire quickly)
- Check that redirect URI matches exactly
- Verify SmashRun credentials in `.env`

### No Runs Found

**Check:**
1. Do you have runs in SmashRun account?
2. Check last sync date in sync state file
3. Try fetching with older date

### Database Locked Error

**Error:** "database is locked"

**Fix:**
- Close any other connections to DuckDB file
- Only one process can write at a time
- Check for stale connections

### Module Import Errors

**Error:** "ModuleNotFoundError"

**Fix:**
```bash
# Make sure you're in project root
cd /path/to/myrunstreak.com

# Activate virtual environment
source .venv/bin/activate

# Or use UV directly
uv run python scripts/test_local_sync.py
```

## 📚 Related Documentation

- [SmashRun OAuth Guide](../docs/SMASHRUN_OAUTH.md)
- [Lambda Sync Documentation](../docs/LAMBDA_SYNC.md)
- [Data Model Guide](../docs/DATA_MODEL.md)

---

🏃‍♂️ Happy testing!
