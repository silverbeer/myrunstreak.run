# Production Deployment Checklist - Phase 7

Quick reference checklist for deploying MyRunStreak.com with Supabase multi-user support.

## Pre-Deployment

### Supabase Setup
- [ ] Create Supabase production project
- [ ] Save project URL: `https://xxxxx.supabase.co`
- [ ] Save service role key: `eyJhbGci...`
- [ ] Link project: `supabase link --project-ref xxxxx`
- [ ] Apply migrations: `supabase db push`
- [ ] Verify tables: users, user_sources, runs, monthly_summary

### AWS Secrets Manager
- [ ] Create Supabase credentials secret:
      ```bash
      aws secretsmanager create-secret \
        --name "myrunstreak/prod/supabase/credentials" \
        --secret-string '{"url":"https://xxxxx.supabase.co","key":"eyJ..."}'
      ```
- [ ] Verify secret exists:
      ```bash
      aws secretsmanager get-secret-value \
        --secret-id "myrunstreak/prod/supabase/credentials"
      ```

### Terraform Variables
- [ ] Update `terraform/environments/prod/terraform.tfvars`:
      ```hcl
      supabase_url              = "https://xxxxx.supabase.co"
      supabase_service_role_key = "eyJ..."
      ```
- [ ] Verify file is in `.gitignore`
- [ ] Confirm all SmashRun OAuth variables are set

### Code Review
- [ ] All Supabase integration code merged to main
- [ ] Local tests pass: `./scripts/test_all_local.sh`
- [ ] Code quality checks pass:
      ```bash
      uv run ruff check .
      uv run ruff format .
      uv run mypy src/
      ```

## Deployment

### Step 1: Terraform Plan
- [ ] Navigate to prod environment: `cd terraform/environments/prod`
- [ ] Initialize: `terraform init`
- [ ] Create plan: `terraform plan -out=tfplan`
- [ ] Review changes:
  - [ ] New Supabase secret resource
  - [ ] Lambda environment variables updated
  - [ ] No unexpected resource deletions

### Step 2: Terraform Apply
- [ ] Apply changes: `terraform apply tfplan`
- [ ] Wait for completion
- [ ] Save any output values

### Step 3: Lambda Deployment
Choose one:

**Option A: GitHub Actions (Recommended)**
- [ ] Push to main branch
- [ ] Monitor GitHub Actions workflow
- [ ] Verify deployment success in Actions tab

**Option B: Manual**
- [ ] Build deployment package:
      ```bash
      cd src
      uv sync --all-extras
      uv export --no-hashes > requirements.txt
      mkdir -p package
      pip install -r requirements.txt -t package/
      cp -r lambdas/* package/
      cp -r shared package/
      cd package && zip -r ../deployment-package.zip .
      ```
- [ ] Deploy sync Lambda:
      ```bash
      aws lambda update-function-code \
        --function-name myrunstreak-sync-runner-prod \
        --zip-file fileb://deployment-package.zip
      ```
- [ ] Deploy query Lambda:
      ```bash
      aws lambda update-function-code \
        --function-name myrunstreak-query-runner-prod \
        --zip-file fileb://deployment-package.zip
      ```

## Verification

### Lambda Configuration
- [ ] Verify sync Lambda environment variables:
      ```bash
      aws lambda get-function-configuration \
        --function-name myrunstreak-sync-runner-prod \
        --query 'Environment.Variables'
      ```
      Expected: SUPABASE_URL, SUPABASE_KEY, SMASHRUN_CLIENT_ID, SMASHRUN_CLIENT_SECRET
- [ ] Verify query Lambda environment variables:
      ```bash
      aws lambda get-function-configuration \
        --function-name myrunstreak-query-runner-prod \
        --query 'Environment.Variables'
      ```
      Expected: SUPABASE_URL, SUPABASE_KEY

### Lambda Execution
- [ ] Invoke sync Lambda manually:
      ```bash
      aws lambda invoke \
        --function-name myrunstreak-sync-runner-prod \
        --payload '{"source":"manual-test"}' \
        response.json && cat response.json
      ```
- [ ] Check response shows success and sources synced
- [ ] Verify CloudWatch logs show no errors:
      ```bash
      aws logs tail /aws/lambda/myrunstreak-sync-runner-prod --since 10m
      ```

### Supabase Data
- [ ] Open Supabase Studio: https://supabase.com/dashboard
- [ ] Check users table has data
- [ ] Check user_sources table has active sources
- [ ] Check runs table has data
- [ ] Verify run counts match expected

### API Endpoints
- [ ] Get API Gateway URL:
      ```bash
      aws apigatewayv2 get-apis \
        --query "Items[?Name=='myrunstreak-api-prod'].ApiEndpoint" \
        --output text
      ```
- [ ] Test overall stats: `curl "$API_URL/stats/overall?user_id=xxxxx"`
- [ ] Test current streak: `curl "$API_URL/stats/current-streak?user_id=xxxxx"`
- [ ] Test monthly summary: `curl "$API_URL/stats/monthly?user_id=xxxxx"`
- [ ] All endpoints return valid JSON (not errors)

### Monitoring
- [ ] CloudWatch logs show no errors
- [ ] No DuckDB references in logs
- [ ] No S3 access errors
- [ ] Token refresh working (check logs for "Refreshed token")
- [ ] EventBridge schedule is enabled

## Post-Deployment (24-48 hours)

### Monitor Metrics
- [ ] Lambda invocations: Should run daily via EventBridge
- [ ] Lambda errors: Should be 0
- [ ] Lambda duration: Should be < 30s per user
- [ ] `MyRunStreak/SourcesSynced`: Should match user count
- [ ] `MyRunStreak/RunsSynced`: Should increase daily
- [ ] `MyRunStreak/SyncFailures`: Should be 0

### Supabase Monitoring
- [ ] Database connections: Should be < 10
- [ ] Query performance: Should be < 100ms
- [ ] Storage usage: Monitor growth
- [ ] No connection errors in logs

### Set Up Alarms
- [ ] Create CloudWatch alarm for Lambda errors
- [ ] Create alarm for sync failures
- [ ] Create alarm for no runs synced in 24 hours
- [ ] Test alarms fire correctly

## Cleanup (After 1 week stable)

### Deprecate DuckDB Infrastructure
- [ ] Confirm no references to DuckDB in logs
- [ ] Comment out S3 module in Terraform
- [ ] Run `terraform plan` to verify S3 removal
- [ ] Run `terraform apply` to remove S3 bucket
- [ ] Update documentation to remove S3 references

### Documentation Updates
- [ ] Update README with new architecture
- [ ] Document deployment process for team
- [ ] Update runbook with Supabase procedures
- [ ] Archive old DuckDB documentation

## Rollback Plan

If issues occur, rollback using:

1. **Restore Lambda environment variables:**
   ```bash
   cd terraform/environments/prod
   git revert HEAD
   terraform apply -auto-approve
   ```

2. **Restore Lambda code:**
   ```bash
   aws lambda update-function-code \
     --function-name myrunstreak-sync-runner-prod \
     --s3-bucket myrunstreak-lambda-packages \
     --s3-key previous-version.zip
   ```

3. **Verify rollback:**
   ```bash
   aws lambda invoke \
     --function-name myrunstreak-sync-runner-prod \
     --payload '{"source":"manual-test"}' \
     response.json
   ```

## Troubleshooting Quick Reference

| Issue | Quick Fix |
|-------|-----------|
| "Failed to connect to database" | Check SUPABASE_URL and SUPABASE_KEY env vars |
| "No active sources found" | Verify user_sources table has is_active=true |
| "Missing user_id parameter" | Add `?user_id=xxxxx` to API requests |
| Lambda timeout | Increase memory or reduce batch size |
| High costs | Reduce LOG_LEVEL to WARNING |

## Sign-Off

**Deployed by:** ________________
**Date:** ________________
**Version:** ________________

**Verified by:** ________________
**Date:** ________________

**Production approval:** ________________
**Date:** ________________

---

For detailed troubleshooting, see [PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md)
