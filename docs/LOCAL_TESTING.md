# Local Testing Guide

Guide for testing MyRunStreak.com components locally without touching production resources.

## Overview

We provide multiple ways to test locally:
1. **Supabase** - Local PostgreSQL database (already set up)
2. **AWS Services** - Mocked with moto or LocalStack
3. **Lambda Functions** - Local invocation scripts

## Prerequisites

```bash
# Install dependencies
uv sync --all-extras

# Start local Supabase
supabase start
```

## Testing Components

### 1. Database & Repositories

Test Supabase infrastructure and repository operations:

```bash
# Test database connection, schema, and repositories
uv run python scripts/test_supabase_local.py
```

**What it tests:**
- ✅ Supabase connection
- ✅ Database schema (tables, views)
- ✅ UsersRepository operations
- ✅ RunsRepository CRUD operations
- ✅ Data mappers

### 2. Sync Lambda (Multi-User)

Test the sync Lambda handler:

```bash
# Test sync Lambda structure and flow
uv run python scripts/test_sync_lambda_local.py
```

**What it tests:**
- ✅ Handler structure and imports
- ✅ Multi-user source iteration
- ✅ Error handling
- ✅ No active sources scenario

### 3. Query Lambda (Multi-User)

Test all query API endpoints:

```bash
# Test query Lambda endpoints
uv run python scripts/test_query_lambda_local.py
```

**What it tests:**
- ✅ All 6 query endpoints
- ✅ User authentication (user_id parameter)
- ✅ Error handling (missing/invalid user_id)
- ✅ Response format validation

### 4. OAuth Token Migration

Test the OAuth token migration script without touching real AWS:

```bash
# Test migration with mocked AWS Secrets Manager
uv run python scripts/test_oauth_migration_local.py
```

**What it tests:**
- ✅ Reading old token structure
- ✅ Creating per-user secrets
- ✅ Database updates
- ✅ Migration validation
- ✅ Automatic rollback

## Local AWS Testing Options

### Option 1: Moto (Built-in, Recommended)

Moto is already included in dev dependencies and mocks AWS services in-memory.

**Pros:**
- ✅ No additional setup
- ✅ Fast execution
- ✅ Included in test scripts
- ✅ Good for CI/CD

**Cons:**
- ⚠️ Limited to specific AWS services
- ⚠️ Some features not fully implemented

**Usage:**
```python
from moto import mock_aws

@mock_aws
def test_function():
    # Your AWS operations here
    # They'll use mocked AWS services
    pass
```

### Option 2: LocalStack (Optional, Comprehensive)

LocalStack provides a full AWS cloud stack locally via Docker.

**Pros:**
- ✅ More realistic AWS environment
- ✅ Supports more AWS services
- ✅ State persistence
- ✅ Web UI available (Pro)

**Cons:**
- ⚠️ Requires Docker
- ⚠️ Slower than moto
- ⚠️ Some features require Pro license

**Setup:**
```bash
# Start LocalStack
docker-compose -f docker-compose.localstack.yml up -d

# Check status
docker-compose -f docker-compose.localstack.yml ps

# View logs
docker-compose -f docker-compose.localstack.yml logs -f

# Stop LocalStack
docker-compose -f docker-compose.localstack.yml down
```

**Configure AWS CLI for LocalStack:**
```bash
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-2
```

**Test with LocalStack:**
```bash
# Create test secret
aws --endpoint-url=http://localhost:4566 secretsmanager create-secret \
  --name myrunstreak/dev/smashrun/oauth \
  --secret-string '{"access_token":"test","refresh_token":"test","expires_at":"2026-01-01T00:00:00Z"}'

# List secrets
aws --endpoint-url=http://localhost:4566 secretsmanager list-secrets

# Run migration
uv run python scripts/migrate_oauth_tokens.py --dry-run
```

## Complete Local Test Suite

Run all tests in sequence:

```bash
#!/bin/bash
# Run complete local test suite

echo "🧪 Running Complete Local Test Suite"
echo "======================================"

# 1. Database tests
echo -e "\n📊 Testing Supabase Infrastructure..."
uv run python scripts/test_supabase_local.py || exit 1

# 2. Sync Lambda tests
echo -e "\n🔄 Testing Sync Lambda..."
uv run python scripts/test_sync_lambda_local.py || exit 1

# 3. Query Lambda tests
echo -e "\n🔍 Testing Query Lambda..."
uv run python scripts/test_query_lambda_local.py || exit 1

# 4. OAuth Migration tests
echo -e "\n🔐 Testing OAuth Migration..."
uv run python scripts/test_oauth_migration_local.py || exit 1

echo -e "\n======================================"
echo "✅ All Local Tests Passed!"
echo "======================================"
```

Save this as `scripts/test_all_local.sh` and run:
```bash
chmod +x scripts/test_all_local.sh
./scripts/test_all_local.sh
```

## Testing Checklist

Before deploying to production:

- [ ] All Supabase tests pass
- [ ] All sync Lambda tests pass
- [ ] All query Lambda tests pass
- [ ] OAuth migration test passes
- [ ] Code quality checks pass (ruff, mypy)
- [ ] Manual testing of critical flows

## Troubleshooting

### Supabase not running
```bash
# Check status
supabase status

# Start if stopped
supabase start

# Reset if corrupted
supabase db reset
```

### Moto tests failing
```bash
# Reinstall dev dependencies
uv sync --all-extras

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
```

### LocalStack not responding
```bash
# Check container status
docker-compose -f docker-compose.localstack.yml ps

# Restart LocalStack
docker-compose -f docker-compose.localstack.yml restart

# View logs for errors
docker-compose -f docker-compose.localstack.yml logs
```

### Test data issues
```bash
# Reset local Supabase (recreates seed data)
supabase db reset

# Verify seed data
uv run python -c "
from src.shared.supabase_client import get_supabase_client
supabase = get_supabase_client()
result = supabase.table('users').select('*').execute()
print(f'Users: {len(result.data)}')
"
```

## CI/CD Integration

These tests can be run in GitHub Actions:

```yaml
# .github/workflows/test.yml
- name: Run Local Tests
  run: |
    # Start Supabase
    supabase start

    # Run all test scripts
    uv run python scripts/test_supabase_local.py
    uv run python scripts/test_sync_lambda_local.py
    uv run python scripts/test_query_lambda_local.py
    uv run python scripts/test_oauth_migration_local.py
```

## References

- [Supabase CLI Docs](https://supabase.com/docs/guides/cli)
- [Moto Documentation](https://docs.getmoto.org/)
- [LocalStack Documentation](https://docs.localstack.cloud/)
- [pytest Documentation](https://docs.pytest.org/)
