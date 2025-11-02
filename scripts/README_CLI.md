# MyRunStreak CLI Client - Local Testing Guide

This guide explains how to test the MyRunStreak API endpoints locally using the provided CLI client.

## Quick Start

1. **Install dependencies** (if not already installed):
   ```bash
   uv sync
   ```

2. **Install optional CLI dependencies for pretty output**:
   ```bash
   uv pip install rich
   ```

3. **Run the CLI**:
   ```bash
   # Basic usage
   uv run python scripts/query_cli.py overall

   # Or make it executable and run directly
   ./scripts/query_cli.py overall
   ```

## CLI Commands

### Overall Statistics
Get overall running statistics (total runs, distance, pace, etc.):
```bash
uv run python scripts/query_cli.py overall
```

**Output:**
```
📊 Overall Running Statistics
Total Runs:       4350
Total Distance:   29841.22 km
Average Distance: 6.86 km
Longest Run:      43.11 km
Average Pace:     5.70 min/km
```

### Recent Runs
Get recent runs (default 10, max 100):
```bash
# Get last 5 runs
uv run python scripts/query_cli.py recent --limit 5

# Get last 20 runs
uv run python scripts/query_cli.py recent --limit 20
```

### Monthly Statistics
Get monthly summaries (default 12 months, max 60):
```bash
# Get last 6 months
uv run python scripts/query_cli.py monthly --limit 6

# Get last 24 months
uv run python scripts/query_cli.py monthly --limit 24
```

### Running Streaks
Get streak analysis with current streak and top 10 streaks:
```bash
uv run python scripts/query_cli.py streaks
```

**Output:**
```
🔥 Current Streak: 114 days
🏆 Longest Streak: 195 days

🎯 Top Streaks
Start        End          Length (days)  Current?
2018-04-01   2018-10-12            195
2025-07-11   2025-11-01            114     ✓
...
```

### Personal Records
Get personal records (longest run, fastest pace, etc.):
```bash
uv run python scripts/query_cli.py records
```

### List All Runs
List all runs with pagination:
```bash
# First 50 runs
uv run python scripts/query_cli.py runs

# Skip first 50, get next 50
uv run python scripts/query_cli.py runs --offset 50 --limit 50

# Get specific page
uv run python scripts/query_cli.py runs --offset 100 --limit 25
```

## Output Formats

### Pretty Tables (with rich)
By default, the CLI uses rich tables for formatted output:
```bash
uv run python scripts/query_cli.py overall
```

### Raw JSON
Get raw JSON output for scripting or debugging:
```bash
# Overall stats as JSON
uv run python scripts/query_cli.py overall --json

# Recent runs as JSON
uv run python scripts/query_cli.py recent --limit 5 --json
```

Example JSON output:
```json
{
  "total_runs": 4350,
  "total_km": 29841.22,
  "avg_km": 6.86,
  "longest_run_km": 43.11,
  "avg_pace_min_per_km": 5.7
}
```

## Environment Variables

### Change API Endpoint
Override the default API endpoint for testing:

```bash
# Test against production (when it exists)
export API_BASE_URL="https://api.myrunstreak.com/v1"
uv run python scripts/query_cli.py overall

# Test against local Lambda (see below)
export API_BASE_URL="http://localhost:9000/2015-03-31/functions/function/invocations"
uv run python scripts/query_cli.py overall
```

## Local Lambda Testing

### Option 1: Test Lambda Locally with AWS SAM

1. **Install AWS SAM CLI**:
   ```bash
   # macOS
   brew install aws-sam-cli

   # Or via pip
   pip install aws-sam-cli
   ```

2. **Create SAM template** (create `template.yaml` in project root):
   ```yaml
   AWSTemplateFormatVersion: '2010-09-09'
   Transform: AWS::Serverless-2016-10-31

   Resources:
     QueryFunction:
       Type: AWS::Serverless::Function
       Properties:
         Handler: lambda_function.handler
         Runtime: python3.12
         CodeUri: ./
         MemorySize: 256
         Timeout: 30
         Environment:
           Variables:
             DUCKDB_PATH: "s3://myrunstreak-data-dev-855323747881/runs.duckdb"
             LOG_LEVEL: "INFO"
   ```

3. **Run Lambda locally**:
   ```bash
   # Build the Lambda package
   sam build

   # Start local API Gateway
   sam local start-api --port 3000

   # Test in another terminal
   curl http://localhost:3000/stats/overall
   ```

### Option 2: Test Lambda with Docker

1. **Build Lambda container**:
   ```bash
   # Create Dockerfile
   cat > Dockerfile.lambda <<EOF
   FROM public.ecr.aws/lambda/python:3.12

   # Copy requirements
   COPY pyproject.toml uv.lock ./

   # Install uv and dependencies
   RUN pip install uv && uv pip install --system .

   # Copy application code
   COPY src/ ./src/
   COPY lambda_function.py ./

   CMD ["lambda_function.handler"]
   EOF

   # Build container
   docker build -t myrunstreak-query -f Dockerfile.lambda .

   # Run container
   docker run -p 9000:8080 \
     -e DUCKDB_PATH="s3://myrunstreak-data-dev-855323747881/runs.duckdb" \
     -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
     -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
     myrunstreak-query
   ```

2. **Test with curl**:
   ```bash
   # Test Lambda directly
   curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
     -d '{
       "resource": "/stats/overall",
       "path": "/stats/overall",
       "httpMethod": "GET",
       "headers": {},
       "queryStringParameters": null,
       "pathParameters": null,
       "body": null
     }'
   ```

### Option 3: Test Direct Python Import

For quick unit testing without Lambda:

```python
# test_local.py
from src.lambdas.query_runs.handler import app

# Simulate API Gateway event
event = {
    "resource": "/stats/overall",
    "path": "/stats/overall",
    "httpMethod": "GET",
    "headers": {},
    "queryStringParameters": None,
    "pathParameters": None,
    "body": None,
    "requestContext": {
        "requestId": "test-request-id",
        "domainName": "localhost",
        "stage": "test"
    }
}

# Mock Lambda context
class MockContext:
    def __init__(self):
        self.function_name = "test"
        self.memory_limit_in_mb = 256
        self.invoked_function_arn = "arn:aws:lambda:us-east-2:123456789:function:test"
        self.aws_request_id = "test-request-id"

# Call handler
response = app.resolve(event, MockContext())
print(response)
```

Run it:
```bash
DUCKDB_PATH="s3://myrunstreak-data-dev-855323747881/runs.duckdb" \
  python test_local.py
```

## Testing with Local DuckDB Database

If you want to test with a local DuckDB file (not S3):

1. **Download database from S3**:
   ```bash
   AWS_PROFILE=silverbeer aws s3 cp \
     s3://myrunstreak-data-dev-855323747881/runs.duckdb \
     ./data/runs.duckdb
   ```

2. **Set environment variable**:
   ```bash
   export DUCKDB_PATH="./data/runs.duckdb"
   ```

3. **Modify Lambda handler temporarily** to use local path:
   ```python
   # In handler.py
   duckdb_path = os.getenv("DUCKDB_PATH", "./data/runs.duckdb")  # Local path
   db_manager = DuckDBManager(duckdb_path, read_only=True)
   ```

4. **Test with CLI**:
   ```bash
   uv run python scripts/query_cli.py overall
   ```

## CI/CD Testing

### Test in GitHub Actions

The deployed endpoints are automatically tested in the deployment workflow:

```yaml
# .github/workflows/lambda-deploy.yml
- name: Smoke Test
  run: |
    RESULT=$(aws lambda invoke \
      --function-name myrunstreak-query-runner-dev \
      --payload '{"source":"github-actions","action":"smoke-test"}' \
      response.json)
```

### Manual API Testing

Test deployed endpoints with curl:

```bash
# Test overall stats
curl https://9fmuhcz4y0.execute-api.us-east-2.amazonaws.com/dev/stats/overall

# Test recent runs
curl "https://9fmuhcz4y0.execute-api.us-east-2.amazonaws.com/dev/runs/recent?limit=5"

# Test streaks
curl https://9fmuhcz4y0.execute-api.us-east-2.amazonaws.com/dev/stats/streaks

# Test with jq for pretty JSON
curl -s https://9fmuhcz4y0.execute-api.us-east-2.amazonaws.com/dev/stats/overall | jq .
```

## Troubleshooting

### "httpx not found"
```bash
uv sync  # Install all dependencies
```

### "DuckDB file not found"
Make sure `DUCKDB_PATH` environment variable points to valid database:
```bash
export DUCKDB_PATH="s3://myrunstreak-data-dev-855323747881/runs.duckdb"
# or
export DUCKDB_PATH="./data/runs.duckdb"  # for local testing
```

### "Binder Error: Referenced column not found"
This means the SQL query is using wrong column names. Check the schema:
```python
# Correct column names
distance_km             # not distance
duration_seconds        # not duration
average_pace_min_per_km # not avgPace
heart_rate_average      # not avgHeartRate
start_date_time_local   # not startDateTimeLocal
activity_id             # not activityId
```

### "Missing Authentication Token"
This error from API Gateway means:
1. The route doesn't exist in API Gateway
2. The API Gateway deployment wasn't updated after adding new routes

To fix:
```bash
# Manually create new deployment
AWS_PROFILE=silverbeer aws apigateway create-deployment \
  --rest-api-id 9fmuhcz4y0 \
  --stage-name dev \
  --region us-east-2
```

## Tips

1. **Use JSON for scripting**: Add `--json` flag for parseable output
2. **Install rich**: `uv pip install rich` for beautiful tables
3. **Combine with jq**: `uv run python scripts/query_cli.py overall --json | jq '.total_runs'`
4. **Create aliases**: Add to your `.bashrc` or `.zshrc`:
   ```bash
   alias runs="uv run python ~/path/to/scripts/query_cli.py"
   # Then use: runs overall, runs streaks, etc.
   ```

## Example Workflows

### Compare monthly progress
```bash
# Get last 12 months
uv run python scripts/query_cli.py monthly --limit 12 --json > monthly_stats.json

# Analyze with jq
jq '.months[] | {month: .month, total_km: .total_km}' monthly_stats.json
```

### Track current streak
```bash
# Get current streak
uv run python scripts/query_cli.py streaks --json | \
  jq '.current_streak'
```

### Export recent runs to CSV
```bash
uv run python scripts/query_cli.py recent --limit 100 --json | \
  jq -r '.runs[] | [.date, .distance_km, .avg_pace_min_per_km] | @csv' > recent_runs.csv
```
