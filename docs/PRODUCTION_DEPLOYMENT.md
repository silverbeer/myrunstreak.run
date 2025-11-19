# Production Deployment Guide - Phase 7

Complete guide for deploying MyRunStreak.com to production with Supabase PostgreSQL and multi-user support.

## Overview

This guide covers the final phase of the Supabase migration - deploying the multi-user architecture to production. The deployment includes:

- Supabase PostgreSQL database (replaces DuckDB)
- Per-user OAuth token management
- Multi-user sync Lambda
- Multi-user query Lambda
- Updated Terraform infrastructure

## Prerequisites

### 1. Supabase Project Setup

Create a production Supabase project:

1. **Create project** at https://supabase.com/dashboard
   - Choose region closest to your AWS region (us-east-2)
   - Select appropriate plan (Free tier for testing, Pro for production)
   - Note the project reference ID

2. **Get credentials:**
   ```bash
   # Project URL (from Settings > API)
   https://your-project-ref.supabase.co

   # Service role key (from Settings > API)
   # This bypasses Row Level Security - keep it secret!
   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```

3. **Apply database migrations:**
   ```bash
   # Link to your production project
   supabase link --project-ref your-project-ref

   # Apply all migrations
   supabase db push

   # Verify schema
   supabase db diff
   ```

4. **Verify tables created:**
   - `users` - User accounts
   - `user_sources` - OAuth integrations
   - `runs` - Running activities
   - `monthly_summary` - Pre-computed stats (view)

### 2. AWS Secrets Manager

Add Supabase credentials to AWS Secrets Manager:

```bash
# Set your AWS profile
export AWS_PROFILE=your-profile-name

# Create Supabase credentials secret
aws secretsmanager create-secret \
  --name "myrunstreak/prod/supabase/credentials" \
  --description "Supabase PostgreSQL database credentials" \
  --secret-string '{
    "url": "https://your-project-ref.supabase.co",
    "key": "your-service-role-key"
  }' \
  --region us-east-2

# Verify secret created
aws secretsmanager get-secret-value \
  --secret-id "myrunstreak/prod/supabase/credentials" \
  --region us-east-2
```

**Security Note:** The service role key bypasses Row Level Security (RLS). Never expose it in client-side code or logs.

### 3. Terraform Variables

Update `terraform/environments/prod/terraform.tfvars` with Supabase credentials:

```hcl
# Supabase Configuration
supabase_url              = "https://your-project-ref.supabase.co"
supabase_service_role_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Existing SmashRun OAuth credentials
smashrun_client_id     = "streak_xxxxx"
smashrun_client_secret = "xxxxx"
smashrun_access_token  = "xxxxx"
smashrun_refresh_token = "xxxxx"

# API Gateway key
api_key_personal = "xxxxx"
```

**Important:** This file should NOT be committed to git. Add it to `.gitignore`.

### 4. User Data Migration

If you have existing users with OAuth tokens in the old structure, run the migration script:

```bash
# Dry run first (safe, no changes)
uv run python scripts/migrate_oauth_tokens.py --dry-run --environment prod

# Review output, then run actual migration
uv run python scripts/migrate_oauth_tokens.py --no-dry-run --environment prod
```

**Note:** If you're starting fresh (no existing users), skip this step. New users will use the new per-user token structure from the start.

## Deployment Steps

### Step 1: Review Terraform Changes

```bash
cd terraform/environments/prod

# Initialize Terraform (if not already done)
AWS_PROFILE=your-profile terraform init

# Review what will change
AWS_PROFILE=your-profile terraform plan -out=tfplan
```

**Expected changes:**
- ✅ New secret: `myrunstreak/prod/supabase/credentials`
- ✅ Lambda environment variables updated (SUPABASE_URL, SUPABASE_KEY)
- ✅ Lambda environment variables removed (DUCKDB_PATH)
- ⚠️ S3 module may show as deprecated (but not destroyed)

**Review carefully:**
- No unexpected resource deletions
- Lambda functions will be updated (requires redeployment)
- API Gateway should not change

### Step 2: Apply Terraform Changes

```bash
# Apply the changes
AWS_PROFILE=your-profile terraform apply tfplan

# Expected output:
# Apply complete! Resources: X added, Y changed, 0 destroyed.
```

**Rollback Plan:** If anything goes wrong, you can revert:
```bash
# Restore previous Lambda environment variables
AWS_PROFILE=your-profile terraform apply \
  -var="supabase_url=" \
  -var="supabase_service_role_key="
```

### Step 3: Deploy Lambda Code

The Lambda code needs to be redeployed with the updated handlers for Supabase.

**Option A: GitHub Actions (Recommended)**

Push to main branch and let CI/CD deploy:
```bash
git push origin feat/phase7-production-deployment

# Or merge PR and push to main
git checkout main
git pull
# GitHub Actions will automatically deploy
```

**Option B: Manual Deployment**

```bash
# Build deployment package
cd src
uv sync --all-extras
uv export --no-hashes > requirements.txt

# Create deployment package
mkdir -p package
pip install -r requirements.txt -t package/
cp -r lambdas/* package/
cp -r shared package/
cd package && zip -r ../deployment-package.zip . && cd ..

# Deploy sync Lambda
AWS_PROFILE=your-profile aws lambda update-function-code \
  --function-name myrunstreak-sync-runner-prod \
  --zip-file fileb://deployment-package.zip \
  --region us-east-2

# Deploy query Lambda
AWS_PROFILE=your-profile aws lambda update-function-code \
  --function-name myrunstreak-query-runner-prod \
  --zip-file fileb://deployment-package.zip \
  --region us-east-2
```

### Step 4: Verify Deployment

#### 4.1 Check Lambda Configuration

```bash
# Verify sync Lambda environment variables
AWS_PROFILE=your-profile aws lambda get-function-configuration \
  --function-name myrunstreak-sync-runner-prod \
  --region us-east-2 \
  --query 'Environment.Variables'

# Should show:
# {
#   "SUPABASE_URL": "https://xxxxx.supabase.co",
#   "SUPABASE_KEY": "eyJ...",
#   "SMASHRUN_CLIENT_ID": "...",
#   "SMASHRUN_CLIENT_SECRET": "...",
#   "SMASHRUN_REDIRECT_URI": "urn:ietf:wg:oauth:2.0:oob"
# }

# Verify query Lambda
AWS_PROFILE=your-profile aws lambda get-function-configuration \
  --function-name myrunstreak-query-runner-prod \
  --region us-east-2 \
  --query 'Environment.Variables'

# Should show:
# {
#   "SUPABASE_URL": "https://xxxxx.supabase.co",
#   "SUPABASE_KEY": "eyJ..."
# }
```

#### 4.2 Test Sync Lambda

```bash
# Invoke sync Lambda manually
AWS_PROFILE=your-profile aws lambda invoke \
  --function-name myrunstreak-sync-runner-prod \
  --payload '{"source":"manual-test"}' \
  --region us-east-2 \
  response.json

# Check response
cat response.json

# Expected output:
# {
#   "statusCode": 200,
#   "message": "Synced X sources successfully",
#   "sources_synced": X,
#   "runs_synced": Y,
#   "failed_sources": []
# }
```

#### 4.3 Check CloudWatch Logs

```bash
# View sync Lambda logs
AWS_PROFILE=your-profile aws logs tail \
  /aws/lambda/myrunstreak-sync-runner-prod \
  --follow \
  --region us-east-2

# Look for:
# - Successful Supabase connections
# - Sources being processed
# - Runs being synced
# - No errors related to DuckDB or S3
```

#### 4.4 Verify Data in Supabase

```bash
# Check data via Supabase Studio
# Go to: https://supabase.com/dashboard/project/your-project-ref/editor

# Or use SQL query
psql "postgresql://postgres:[password]@db.your-project-ref.supabase.co:5432/postgres"

# Check users
SELECT id, email, created_at FROM users;

# Check user sources
SELECT id, user_id, source_type, is_active FROM user_sources;

# Check runs
SELECT COUNT(*), user_id FROM runs GROUP BY user_id;
```

#### 4.5 Test Query Endpoints

```bash
# Get your API endpoint
API_URL=$(AWS_PROFILE=your-profile aws apigatewayv2 get-apis \
  --query "Items[?Name=='myrunstreak-api-prod'].ApiEndpoint" \
  --output text \
  --region us-east-2)

# Test overall stats (requires user_id parameter)
curl "$API_URL/stats/overall?user_id=YOUR_USER_ID"

# Test current streak
curl "$API_URL/stats/current-streak?user_id=YOUR_USER_ID"

# Test monthly summary
curl "$API_URL/stats/monthly?user_id=YOUR_USER_ID"

# All endpoints should return JSON data, not errors
```

## Post-Deployment Validation

### Automated Checks

Run the validation script:

```bash
uv run python scripts/validate_production_deployment.py
```

This checks:
- ✅ Lambda functions are deployed
- ✅ Environment variables are correct
- ✅ Supabase connection works
- ✅ API Gateway endpoints respond
- ✅ CloudWatch logs show no errors

### Manual Verification Checklist

- [ ] Sync Lambda runs successfully
- [ ] CloudWatch logs show no errors
- [ ] Supabase has user data
- [ ] All query endpoints return data
- [ ] No DuckDB references in logs
- [ ] No S3 access errors
- [ ] Token refresh works correctly
- [ ] EventBridge schedule is enabled

### Monitor for 24 Hours

Keep an eye on these metrics:

**CloudWatch Metrics:**
- `MyRunStreak/SourcesSynced` - Should match number of active users
- `MyRunStreak/RunsSynced` - Should increase after each sync
- `MyRunStreak/SyncFailures` - Should remain at zero
- Lambda errors - Should be zero
- Lambda duration - Should be < 30 seconds per user

**Supabase Metrics** (in Supabase Studio):
- Database connections - Should be < 10
- Query performance - Should be < 100ms
- Storage usage - Monitor growth rate

**Set up CloudWatch Alarms:**

```bash
# Alarm for Lambda errors
AWS_PROFILE=your-profile aws cloudwatch put-metric-alarm \
  --alarm-name myrunstreak-lambda-errors \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=myrunstreak-sync-runner-prod

# Alarm for no runs synced in 24 hours
AWS_PROFILE=your-profile aws cloudwatch put-metric-alarm \
  --alarm-name myrunstreak-no-runs-synced \
  --alarm-description "Alert if no runs synced in 24 hours" \
  --metric-name RunsSynced \
  --namespace MyRunStreak \
  --statistic Sum \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator LessThanThreshold
```

## Rollback Procedure

If you need to rollback to the DuckDB version:

### Step 1: Restore Lambda Environment Variables

```bash
cd terraform/environments/prod

# Revert to previous Terraform configuration
git revert HEAD  # Or checkout previous commit

# Apply previous configuration
AWS_PROFILE=your-profile terraform apply -auto-approve
```

### Step 2: Restore Lambda Code

```bash
# Deploy previous Lambda package
AWS_PROFILE=your-profile aws lambda update-function-code \
  --function-name myrunstreak-sync-runner-prod \
  --s3-bucket myrunstreak-lambda-packages \
  --s3-key previous-version.zip \
  --region us-east-2
```

### Step 3: Verify Rollback

```bash
# Test Lambda
AWS_PROFILE=your-profile aws lambda invoke \
  --function-name myrunstreak-sync-runner-prod \
  --payload '{"source":"manual-test"}' \
  --region us-east-2 \
  response.json

# Check logs for DuckDB operations
AWS_PROFILE=your-profile aws logs tail \
  /aws/lambda/myrunstreak-sync-runner-prod \
  --since 1h \
  --region us-east-2
```

## Troubleshooting

### Lambda can't connect to Supabase

**Symptoms:**
- Errors: "Failed to connect to database"
- Logs show connection timeouts

**Solutions:**
1. Verify environment variables:
   ```bash
   AWS_PROFILE=your-profile aws lambda get-function-configuration \
     --function-name myrunstreak-sync-runner-prod \
     --query 'Environment.Variables'
   ```

2. Check Supabase project status at https://status.supabase.com

3. Verify service role key is correct:
   ```bash
   curl https://your-project-ref.supabase.co/rest/v1/users \
     -H "apikey: your-service-role-key" \
     -H "Authorization: Bearer your-service-role-key"
   ```

4. Check VPC/security groups if using VPC

### No users or runs syncing

**Symptoms:**
- Sync Lambda completes but no data in Supabase
- Logs show "No active sources found"

**Solutions:**
1. Check if users exist in database:
   ```sql
   SELECT * FROM users;
   SELECT * FROM user_sources WHERE is_active = true;
   ```

2. Verify OAuth tokens migrated correctly:
   ```bash
   AWS_PROFILE=your-profile aws secretsmanager list-secrets \
     --filters Key=name,Values=myrunstreak/users \
     --region us-east-2
   ```

3. Check SmashRun API is working:
   ```bash
   # Test token manually
   curl https://api.smashrun.com/v1/my/activities/search \
     -H "Authorization: Bearer your-access-token"
   ```

### Query endpoints returning 500 errors

**Symptoms:**
- API requests fail with 500 Internal Server Error
- CloudWatch logs show "Missing user_id parameter"

**Solutions:**
1. Ensure user_id is included in all requests:
   ```bash
   # Wrong
   curl "$API_URL/stats/overall"

   # Correct
   curl "$API_URL/stats/overall?user_id=YOUR_USER_ID"
   ```

2. Verify query Lambda has correct environment variables

3. Check CloudWatch logs for specific errors:
   ```bash
   AWS_PROFILE=your-profile aws logs tail \
     /aws/lambda/myrunstreak-query-runner-prod \
     --filter-pattern "ERROR" \
     --region us-east-2
   ```

### High Lambda costs

**Symptoms:**
- Lambda execution time > 60 seconds per sync
- High CloudWatch costs from verbose logging

**Solutions:**
1. Reduce log verbosity:
   ```bash
   # Set LOG_LEVEL to WARNING instead of INFO
   AWS_PROFILE=your-profile aws lambda update-function-configuration \
     --function-name myrunstreak-sync-runner-prod \
     --environment "Variables={LOG_LEVEL=WARNING,...}"
   ```

2. Optimize query performance in Supabase:
   ```sql
   -- Add indexes if needed
   CREATE INDEX IF NOT EXISTS idx_runs_user_date ON runs(user_id, start_datetime_local);
   ```

3. Consider increasing Lambda memory (faster CPU):
   ```bash
   AWS_PROFILE=your-profile aws lambda update-function-configuration \
     --function-name myrunstreak-sync-runner-prod \
     --memory-size 1024
   ```

## Architecture Changes

### Before (DuckDB)

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

### After (Supabase)

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

## Cost Comparison

### Before (DuckDB)
- S3 storage: ~$0.023/GB/month
- S3 requests: ~$0.005/1000 requests
- Lambda compute: ~$0.20/million requests
- **Total estimated: $5-10/month**

### After (Supabase)
- Supabase Free tier: $0/month (up to 500MB, 2GB bandwidth)
- Supabase Pro: $25/month (8GB database, 250GB bandwidth)
- Lambda compute: ~$0.20/million requests
- **Total estimated: $0-30/month depending on tier**

## Next Steps

After successful deployment:

1. **Monitor for 24-48 hours** - Watch for any errors or issues

2. **Deprecate S3 module** - Once stable, remove S3 bucket from Terraform:
   ```bash
   # After confirming everything works
   # Comment out S3 module in terraform/environments/prod/main.tf
   # Run: terraform apply
   ```

3. **Set up automated backups** - Supabase Pro includes daily backups, or set up custom:
   ```bash
   # Automated PostgreSQL backup
   pg_dump "postgresql://..." > backup.sql
   aws s3 cp backup.sql s3://myrunstreak-backups/
   ```

4. **Enable monitoring dashboards** - Set up CloudWatch or Datadog

5. **Document for team** - Update team wiki with deployment process

## Support

If you encounter issues not covered in this guide:

1. Check CloudWatch logs first
2. Review Supabase Studio for database issues
3. Consult [Supabase documentation](https://supabase.com/docs)
4. Check [AWS Lambda troubleshooting](https://docs.aws.amazon.com/lambda/latest/dg/troubleshooting.html)

## References

- [Supabase Production Checklist](https://supabase.com/docs/guides/platform/going-into-prod)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [Terraform Best Practices](https://www.terraform-best-practices.com/)
- [MyRunStreak Migration Guide](./SUPABASE_MIGRATION.md)
