# Local Testing Quick Start

## Step 1: Start Local Supabase

```bash
# Start Supabase (PostgreSQL database)
supabase start

# Verify it's running
supabase status
```

You should see:
```
API URL: http://127.0.0.1:54321
Database URL: postgresql://postgres:postgres@127.0.0.1:54322/postgres
```

## Step 2: Run All Tests

```bash
# Run complete test suite (all 4 tests)
./scripts/test_all_local.sh
```

This will test:
1. ✅ Supabase Infrastructure (database, repositories)
2. ✅ Sync Lambda (multi-user)
3. ✅ Query Lambda (multi-user)
4. ✅ OAuth Token Migration

**Expected result:** All tests pass ✅

## Step 3: Test Individual Components (Optional)

### Test Database Only
```bash
uv run python scripts/test_supabase_local.py
```

### Test Sync Lambda Only
```bash
uv run python scripts/test_sync_lambda_local.py
```

### Test Query Lambda Only
```bash
uv run python scripts/test_query_lambda_local.py
```

### Test OAuth Migration Only
```bash
uv run python scripts/test_oauth_migration_local.py
```

## What Gets Tested?

### Supabase Infrastructure
- Connection to local database
- All tables exist (users, user_sources, runs, splits, etc.)
- Repository operations work (create, read, update, delete)
- Data mappers convert correctly

### Sync Lambda
- Handler imports and structure
- Multi-user source iteration
- Error handling for no active sources
- Supabase connection from Lambda

### Query Lambda
- All 6 API endpoints (/stats/overall, /runs/recent, etc.)
- User authentication (user_id parameter)
- Error handling (missing/invalid user_id)
- Response format validation

### OAuth Migration
- Reading old OAuth token structure
- Creating new per-user secrets (mocked AWS)
- Updating database with new secret paths
- Migration validation
- Automatic rollback

## Troubleshooting

### Supabase not running?
```bash
# Check status
supabase status

# Start if stopped
supabase start

# Reset if issues
supabase db reset
```

### Tests failing?
```bash
# Reinstall dependencies
uv sync --all-extras

# Check Supabase is running
supabase status

# Run individual test to see specific error
uv run python scripts/test_supabase_local.py
```

### Want to see more detail?
All test scripts output detailed progress:
- ✅ Green checkmarks for success
- ❌ Red X for failures
- Detailed error messages if something goes wrong

## Next Steps

Once all local tests pass:
1. You can confidently run the migration script against real AWS
2. Deploy updated Lambdas to production
3. The code has been validated locally first!

## Need Help?

- See `docs/LOCAL_TESTING.md` for comprehensive guide
- See `docs/SUPABASE_MIGRATION.md` for migration details
- Check individual test script output for specific errors
