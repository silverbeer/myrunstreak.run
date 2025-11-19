# Supabase Migration Guide

Complete guide for migrating MyRunStreak.com from DuckDB to Supabase PostgreSQL with multi-user support.

## Overview

This migration transforms the application from a single-user architecture using DuckDB to a multi-user architecture using Supabase PostgreSQL.

### Migration Phases

- ✅ **Phase 1-3**: Supabase Infrastructure (PR #7)
  - Local Supabase setup
  - Database schema with multi-user support
  - Repository pattern implementation

- ✅ **Phase 4**: Multi-User Sync Lambda (PR #8)
  - Refactored to iterate over all active user sources
  - Per-user OAuth token management
  - Database-tracked sync state

- ✅ **Phase 5**: Multi-User Query Lambda (PR #9)
  - All endpoints require `user_id` parameter
  - Supabase-based data access
  - Proper error handling for authentication

- 🚧 **Phase 6**: OAuth Token Migration (Current)
  - Script to migrate tokens to per-user structure
  - AWS Secrets Manager reorganization

- ⏳ **Phase 7**: Production Deployment
  - Terraform updates for Supabase
  - Environment variable configuration
  - Lambda deployment

## Phase 6: OAuth Token Migration

### Local Testing Options

Before running the migration against real AWS resources, you can test locally:

#### Option 1: Moto (Recommended, Built-in)

Uses moto to mock AWS Secrets Manager - no additional setup required:

```bash
# Run local migration test
uv run python scripts/test_oauth_migration_local.py
```

This test:
- ✅ Creates mock AWS Secrets Manager
- ✅ Sets up test OAuth token in old structure
- ✅ Runs full migration flow
- ✅ Validates migration success
- ✅ Automatically rolls back changes
- ✅ No real AWS resources touched

**Output:**
```
============================================================
🧪 Testing OAuth Token Migration Locally
============================================================

🔧 Setting up mock AWS Secrets Manager...
✅ Created old secret

🔗 Connecting to local Supabase...
✅ Found 1 active source(s)

🔄 Starting migration test...
✅ Created new secret
✅ Updated database
✅ Validation passed

============================================================
🎉 All Migration Tests Passed!
============================================================

✅ Migration script logic validated
✅ Ready for production migration
```

#### Option 2: LocalStack (Optional, More Comprehensive)

For a more realistic AWS environment emulation:

```bash
# Start LocalStack
docker-compose -f docker-compose.localstack.yml up -d

# Configure environment to use LocalStack
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-2

# Create test secret in LocalStack
aws --endpoint-url=http://localhost:4566 secretsmanager create-secret \
  --name myrunstreak/dev/smashrun/oauth \
  --secret-string '{"access_token":"test","refresh_token":"test","expires_at":"2026-01-01T00:00:00Z"}'

# Run migration (dry-run)
uv run python scripts/migrate_oauth_tokens.py --dry-run

# Stop LocalStack when done
docker-compose -f docker-compose.localstack.yml down
```

### Token Structure Migration

**Old Structure (Single-User):**
```
myrunstreak/dev/smashrun/oauth
└── {
      "access_token": "...",
      "refresh_token": "...",
      "expires_at": "..."
    }
```

**New Structure (Multi-User):**
```
myrunstreak/users/{user_id}/sources/{source_type}/tokens
└── {
      "access_token": "...",
      "refresh_token": "...",
      "expires_at": "..."
    }
```

### Migration Script

The migration script (`scripts/migrate_oauth_tokens.py`) performs the following:

1. **Reads old token** from single-user secret
2. **Creates per-user secrets** with new path structure
3. **Updates database** with new secret paths
4. **Validates** migration success

### Running the Migration

#### Dry Run (Recommended First)

```bash
# Default is dry-run (safe)
uv run python scripts/migrate_oauth_tokens.py

# Or explicit dry-run
uv run python scripts/migrate_oauth_tokens.py --dry-run
```

#### Actual Migration

```bash
# Development environment
uv run python scripts/migrate_oauth_tokens.py --no-dry-run

# Production environment (USE WITH CAUTION)
uv run python scripts/migrate_oauth_tokens.py --no-dry-run --environment prod
```

#### Custom Configuration

```bash
# Specify custom secret name and region
uv run python scripts/migrate_oauth_tokens.py \
  --no-dry-run \
  --old-secret "myrunstreak/prod/smashrun/oauth" \
  --region "us-west-2"
```

### Migration Checklist

Before running migration:
- [ ] Verify local Supabase is running: `supabase status`
- [ ] Verify old secret exists in AWS Secrets Manager
- [ ] Check active sources: `scripts/test_supabase_local.py`
- [ ] Run dry-run first: `scripts/migrate_oauth_tokens.py --dry-run`
- [ ] Review dry-run output for any issues

After migration:
- [ ] Verify new secrets created in AWS Secrets Manager
- [ ] Verify database updated with new secret paths
- [ ] Test sync Lambda with new structure
- [ ] Verify token refresh still works

### Rollback

If migration fails, you can rollback by:

1. **Restore old secret paths in database:**
```sql
UPDATE user_sources
SET access_token_secret = 'myrunstreak/dev/smashrun/oauth'
WHERE source_type = 'smashrun';
```

2. **Delete new per-user secrets** (optional):
```bash
# Via AWS CLI
aws secretsmanager delete-secret \
  --secret-id "myrunstreak/users/{user_id}/sources/smashrun/tokens" \
  --force-delete-without-recovery
```

## Phase 7: Production Deployment

### Prerequisites

1. **Supabase Project**
   - Create production Supabase project at https://supabase.com
   - Note the project URL and service role key
   - Apply migrations: `supabase db push`

2. **AWS Secrets Manager**
   - Migrate OAuth tokens using Phase 6 script
   - Add Supabase credentials:
     ```bash
     aws secretsmanager create-secret \
       --name "myrunstreak/prod/supabase" \
       --secret-string '{
         "url": "https://your-project.supabase.co",
         "key": "your-service-role-key"
       }'
     ```

3. **Environment Variables**
   - Update Lambda environment variables in Terraform
   - Add `SUPABASE_URL` and `SUPABASE_KEY`

### Deployment Steps

#### 1. Update Terraform Configuration

```hcl
# terraform/lambda.tf
resource "aws_lambda_function" "sync_runner" {
  # ... existing config ...

  environment {
    variables = {
      SUPABASE_URL = data.aws_secretsmanager_secret_version.supabase.secret_string["url"]
      SUPABASE_KEY = data.aws_secretsmanager_secret_version.supabase.secret_string["key"]
      # Remove DUCKDB_PATH
    }
  }
}
```

#### 2. Deploy Infrastructure

```bash
cd terraform
terraform plan -out=tfplan
terraform apply tfplan
```

#### 3. Deploy Lambda Code

The GitHub Actions workflow will automatically deploy when code is pushed to main.

Or manually:
```bash
# Via AWS CLI
aws lambda update-function-code \
  --function-name myrunstreak-sync-runner-prod \
  --zip-file fileb://deployment-package.zip
```

#### 4. Verify Deployment

```bash
# Test sync Lambda
aws lambda invoke \
  --function-name myrunstreak-sync-runner-prod \
  --payload '{"source":"manual-test"}' \
  response.json

# Test query Lambda
curl "https://api.myrunstreak.com/stats/overall?user_id={user_id}"
```

### Post-Deployment Validation

- [ ] Verify sync Lambda runs successfully
- [ ] Check CloudWatch logs for errors
- [ ] Verify runs syncing to Supabase
- [ ] Test all query endpoints
- [ ] Monitor for any errors over 24 hours
- [ ] Verify token refresh works
- [ ] Check Supabase Studio for data

### Monitoring

**CloudWatch Metrics:**
- `MyRunStreak/SourcesSynced` - Should match number of users
- `MyRunStreak/RunsSynced` - Should increase daily
- `MyRunStreak/SyncFailures` - Should be zero

**Supabase Metrics:**
- Database connections
- Query performance
- Storage usage

**Alerts to Set Up:**
- Lambda errors > 5 in 5 minutes
- Sync failures > 0
- No runs synced in 24 hours

## Troubleshooting

### Migration Issues

**Problem:** Old secret not found
```
Solution: Ensure OAuth tokens initialized first
Check: aws secretsmanager get-secret-value --secret-id myrunstreak/dev/smashrun/oauth
```

**Problem:** Permission denied creating secrets
```
Solution: Ensure Lambda execution role has secretsmanager:CreateSecret permission
Check IAM policies in Terraform
```

**Problem:** Database update fails
```
Solution: Verify Supabase credentials are correct
Check: Connection works locally with test scripts
```

### Lambda Issues

**Problem:** Lambda can't connect to Supabase
```
Solution: Check environment variables SUPABASE_URL and SUPABASE_KEY
Verify: Service role key has correct permissions
```

**Problem:** Token refresh fails
```
Solution: Verify new secret exists and has correct structure
Check: aws secretsmanager get-secret-value --secret-id {new-path}
```

**Problem:** No runs syncing
```
Solution: Check CloudWatch logs for specific errors
Verify: User sources are marked as active in database
```

## Architecture Diagrams

### Before Migration
```
┌─────────────────┐
│  EventBridge    │
│  (Daily Sync)   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Sync Lambda                    │
│  - Single user                  │
│  - Fixed OAuth secret           │
│  - DuckDB on S3                 │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────┐
│  S3 Bucket      │
│  runs.duckdb    │
└─────────────────┘
```

### After Migration
```
┌─────────────────┐
│  EventBridge    │
│  (Daily Sync)   │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  Sync Lambda (Multi-User)            │
│  - Iterates all active sources       │
│  - Per-user OAuth tokens             │
│  - Supabase PostgreSQL               │
└────────┬─────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Supabase PostgreSQL                │
│  - users table                      │
│  - user_sources (OAuth paths)       │
│  - runs (partitioned by user)       │
│  - monthly_summary view             │
└─────────────────────────────────────┘
```

## References

- [Supabase Documentation](https://supabase.com/docs)
- [AWS Secrets Manager Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
- [Lambda Powertools](https://docs.powertools.aws.dev/lambda/python/)
- [PostgreSQL Row Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
