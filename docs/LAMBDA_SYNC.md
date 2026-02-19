**# Lambda Daily Sync Function

Automated daily synchronization of SmashRun runs to DuckDB on S3.

## 🎯 Overview

The daily sync Lambda function runs automatically every day to:
1. **Fetch** new runs from SmashRun API
2. **Parse** run data into typed models
3. **Store** runs in DuckDB database on S3
4. **Track** sync state for incremental updates
5. **Monitor** with metrics, logs, and tracing

## 🏗️ Architecture

```
EventBridge (daily)
    ↓ (trigger)
Lambda Function
    ↓
TokenManager → AWS Secrets Manager (OAuth tokens)
    ↓
SmashRunAPIClient → SmashRun API (fetch runs)
    ↓
Activity Models → Validation
    ↓
DuckDBManager → S3 (store runs)
    ↓
SyncStateManager → AWS Secrets Manager (track last sync)
    ↓
CloudWatch (logs, metrics, traces)
```

## 🔑 Components

### 1. Token Manager (`src/shared/smashrun/token_manager.py`)

**Purpose:** Manage OAuth tokens with automatic refresh

**Features:**
- Fetch tokens from AWS Secrets Manager
- Auto-refresh at the halfway point of token lifetime (~6 weeks for 12-week tokens)
- Update stored tokens after refresh, keeping both access and refresh tokens rolling
- Fallback: refresh within 30 days of expiry if token issue date is unknown

**Key Methods:**
- `get_valid_access_token()` - Returns valid token, refreshes if needed
- `update_tokens()` - Store new tokens in Secrets Manager
- `initialize_tokens()` - First-time token setup

### 2. Sync State Manager (`src/shared/smashrun/sync_state.py`)

**Purpose:** Track when runs were last synced

**Features:**
- Store last sync date in Secrets Manager
- Default to 30 days ago if never synced
- Track sync attempts (success/failure)
- Record number of runs synced

**Key Methods:**
- `get_last_sync_date()` - Get date of last successful sync
- `update_last_sync_date()` - Record successful sync
- `record_sync_attempt()` - Log sync attempt details

### 3. Lambda Handler (`src/lambdas/sync_runs/handler.py`)

**Purpose:** Main Lambda entry point

**Process Flow:**
1. Initialize OAuth and token manager
2. Get valid access token (auto-refreshes)
3. Fetch last sync date
4. Sync runs since last sync
5. Update sync state
6. Emit metrics and logs

**AWS Lambda Powertools Integration:**
- **Logger** - Structured JSON logging
- **Tracer** - X-Ray distributed tracing
- **Metrics** - CloudWatch custom metrics

## 📊 Metrics Emitted

The Lambda function emits these CloudWatch metrics:

| Metric | Type | Description |
|--------|------|-------------|
| `RunsSynced` | Count | Number of runs synced |
| `SyncSuccess` | Count | Successful sync (1) |
| `SyncFailures` | Count | Failed syncs |
| `TokenRefreshes` | Count | Token refresh attempts |
| `ColdStart` | Count | Lambda cold starts |

**Namespace:** `MyRunStreak`
**Service:** `smashrun-sync`

## 🔧 Setup Instructions

### Prerequisites

1. **SmashRun OAuth Tokens**
   - Run the setup script (see below)
   - Tokens stored in Secrets Manager

2. **AWS Resources**
   - S3 bucket for DuckDB database
   - Secrets Manager secrets (tokens, sync state)
   - Lambda execution role with permissions
   - EventBridge schedule rule

### Step 1: Get SmashRun Tokens

Use the setup script to complete OAuth flow:

```bash
# Make sure .env is configured with your SmashRun credentials
cp .env.example .env
# Edit .env with CLIENT_ID and CLIENT_SECRET

# Run setup script
python scripts/setup_smashrun_tokens.py
```

This script will:
1. Generate authorization URL
2. Guide you through OAuth flow
3. Exchange code for tokens
4. Store tokens in AWS Secrets Manager

**Secrets Created:**
- `myrunstreak/smashrun/tokens` - OAuth tokens
- `myrunstreak/sync-state` - Sync state tracking

### Step 2: Deploy Lambda Function

Deploy with Terraform (see Terraform documentation):

```bash
cd terraform/environments/dev
terraform apply
```

Or manually deploy:

```bash
# Package Lambda function
# (See deployment section below)

# Create Lambda function
aws lambda create-function \
    --function-name myrunstreak-sync \
    --runtime python3.12 \
    --handler src.lambdas.sync_runs.handler.lambda_handler \
    --role arn:aws:iam::ACCOUNT:role/myrunstreak-lambda-role \
    --zip-file fileb://lambda.zip \
    --timeout 300 \
    --memory-size 512 \
    --environment Variables="{
        SMASHRUN_CLIENT_ID=your-client-id,
        SMASHRUN_CLIENT_SECRET=your-secret,
        DUCKDB_PATH=s3://myrunstreak-data/runs.duckdb,
        AWS_REGION=us-east-2
    }"
```

### Step 3: Set Up EventBridge Schedule

Create daily trigger:

```bash
# Create EventBridge rule (daily at 6 AM UTC)
aws events put-rule \
    --name myrunstreak-daily-sync \
    --schedule-expression "cron(0 6 * * ? *)" \
    --description "Daily SmashRun sync"

# Add Lambda as target
aws events put-targets \
    --rule myrunstreak-daily-sync \
    --targets "Id=1,Arn=arn:aws:lambda:REGION:ACCOUNT:function:myrunstreak-sync"

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
    --function-name myrunstreak-sync \
    --statement-id EventBridgeInvoke \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:REGION:ACCOUNT:rule/myrunstreak-daily-sync
```

## 📦 Lambda Deployment Package

### Required Permissions

Lambda execution role needs:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:UpdateSecret",
        "secretsmanager:CreateSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-2:*:secret:myrunstreak/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::myrunstreak-data/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords"
      ],
      "Resource": "*"
    }
  ]
}
```

### Environment Variables

Required environment variables:

```bash
SMASHRUN_CLIENT_ID=your-client-id
SMASHRUN_CLIENT_SECRET=your-client-secret
SMASHRUN_REDIRECT_URI=http://localhost:8000/callback  # Not used by Lambda, but required by settings
DUCKDB_PATH=s3://myrunstreak-data/runs.duckdb
AWS_REGION=us-east-2
ENVIRONMENT=prod
LOG_LEVEL=INFO
```

## 🔍 Monitoring & Troubleshooting

### CloudWatch Logs

View logs in CloudWatch:

```bash
# Tail logs
aws logs tail /aws/lambda/myrunstreak-sync --follow

# Search for errors
aws logs filter-log-events \
    --log-group-name /aws/lambda/myrunstreak-sync \
    --filter-pattern "ERROR"
```

### CloudWatch Metrics

View metrics in CloudWatch dashboard:

```bash
aws cloudwatch get-metric-statistics \
    --namespace MyRunStreak \
    --metric-name RunsSynced \
    --dimensions Name=service,Value=smashrun-sync \
    --start-time 2024-10-01T00:00:00Z \
    --end-time 2024-10-31T23:59:59Z \
    --period 86400 \
    --statistics Sum
```

### X-Ray Tracing

View distributed traces in X-Ray console:
- Service map shows dependencies
- Traces show execution timeline
- Identify performance bottlenecks

### Common Issues

**1. Token Expired**
- **Error:** `KeyError: 'access_token'` or "401 Unauthorized" from SmashRun API
- **Cause:** Both access and refresh tokens share the same ~12-week lifespan. If the Lambda was offline long enough for both to expire, auto-refresh fails.
- **Fix:** Re-authorize with SmashRun: `uv run python scripts/get_oauth_tokens.py`, then update the secret in Secrets Manager

**2. Rate Limited**
- **Error:** "429 Too Many Requests"
- **Fix:** SmashRun limits to 250 req/hour; adjust sync frequency

**3. DuckDB Lock**
- **Error:** "Database is locked"
- **Fix:** S3-based DuckDB can have concurrency issues; ensure only one sync runs at a time

**4. No Runs Synced**
- **Check:** Last sync date in Secrets Manager
- **Check:** SmashRun account has runs in date range
- **Check:** CloudWatch logs for errors

## 🧪 Testing

### Local Testing

Test locally without deploying:

```python
# test_local_sync.py
import os
from datetime import date
from src.lambdas.sync_runs.handler import lambda_handler

# Set environment variables
os.environ["SMASHRUN_CLIENT_ID"] = "your-id"
os.environ["SMASHRUN_CLIENT_SECRET"] = "your-secret"
os.environ["DUCKDB_PATH"] = "./data/runs.duckdb"

# Mock Lambda context
class Context:
    function_name = "test"
    memory_limit_in_mb = 512
    invoked_function_arn = "arn:test"
    aws_request_id = "test-123"

# Invoke handler
event = {}
context = Context()
response = lambda_handler(event, context)
print(response)
```

### Manual Invocation

Invoke deployed Lambda:

```bash
# Test invocation
aws lambda invoke \
    --function-name myrunstreak-sync \
    --payload '{}' \
    response.json

# View response
cat response.json
```

## 📈 Performance Optimization

### Cold Start Optimization

- **Provisioned Concurrency:** Keep 1 instance warm
- **Memory:** 512 MB (balance between cost and speed)
- **Timeout:** 5 minutes (300 seconds)

### DuckDB on S3

- **Caching:** Lambda can cache DB file in `/tmp` (512 MB limit)
- **Incremental Sync:** Only fetch new runs since last sync
- **Batch Size:** Fetch 100 runs per API request (SmashRun max)

### Cost Optimization

**Estimated Monthly Cost (running daily):**
- Lambda: ~$0.20 (30 invocations × 30s × 512MB)
- S3: ~$0.02 (1 GB storage + requests)
- Secrets Manager: $0.40 per secret × 2 = $0.80
- CloudWatch Logs: ~$0.50 (depends on logging)

**Total: ~$1.50/month**

## 🚀 Next Steps

After deploying the sync Lambda:

1. **Analytics API** - Query endpoints for streak, stats, PRs
2. **Monitoring Dashboard** - CloudWatch dashboard for metrics
3. **Alerting** - SNS notifications for sync failures
4. **Backup** - Automated S3 backups of DuckDB file
5. **Multi-Region** - Deploy in multiple regions for redundancy

## 📚 Related Documentation

- [SmashRun OAuth Guide](SMASHRUN_OAUTH.md)
- [Data Model Documentation](DATA_MODEL.md)
- [Terraform Infrastructure](../terraform/README.md)
- [API Endpoints](API.md) (coming soon)

---

🏃‍♂️ This Lambda function enables fully automated running streak tracking!
