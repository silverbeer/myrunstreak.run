**# SmashRun OAuth Integration Guide

Complete guide to authenticating with SmashRun API and fetching your running data.

## 🎯 Overview

MyRunStreak.com uses OAuth 2.0 to securely access your SmashRun running data. This guide covers:
1. Getting SmashRun API credentials
2. Setting up OAuth flow
3. Fetching run data
4. Refreshing tokens

## 📋 Prerequisites

- SmashRun account with run data
- Python environment set up (UV installed)
- MyRunStreak.com project cloned

## Step 1: Get SmashRun API Credentials

### Create SmashRun API Application

1. Go to https://smashrun.com/settings/api
2. Log in with your SmashRun account
3. Click "Create New Application"
4. Fill in the application details:
   - **Name:** MyRunStreak (or whatever you prefer)
   - **Description:** Personal running streak tracker
   - **Redirect URI:** `http://localhost:8000/callback` (for local development)
5. Click "Create"
6. Copy your **Client ID** and **Client Secret**

⚠️ **Important:** Keep your Client Secret safe! Never commit it to version control.

## Step 2: Configure Environment

### Create `.env` File

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your credentials
```

### Add Your Credentials

Edit `.env`:

```bash
# SmashRun OAuth Credentials
SMASHRUN_CLIENT_ID=your-actual-client-id-here
SMASHRUN_CLIENT_SECRET=your-actual-client-secret-here
SMASHRUN_REDIRECT_URI=http://localhost:8000/callback

# DuckDB (local development)
DUCKDB_PATH=./data/runs.duckdb

# AWS Configuration
AWS_REGION=us-east-2

# Application Settings
ENVIRONMENT=dev
LOG_LEVEL=INFO
```

## Step 3: OAuth Flow (Interactive)

The OAuth flow requires user interaction to authorize the application.

### Python Example: Complete OAuth Flow

```python
from src.shared.config import get_settings
from src.shared.smashrun import SmashRunOAuthClient

# Load configuration
settings = get_settings()

# Create OAuth client
oauth_client = SmashRunOAuthClient(
    client_id=settings.smashrun_client_id,
    client_secret=settings.smashrun_client_secret,
    redirect_uri=settings.smashrun_redirect_uri,
)

# Step 1: Generate authorization URL
auth_url = oauth_client.get_authorization_url(state="random_state_123")
print(f"Visit this URL to authorize: {auth_url}")

# Step 2: User visits URL and authorizes
# SmashRun redirects back to: http://localhost:8000/callback?code=AUTH_CODE&state=random_state_123

# Step 3: Exchange authorization code for access token
authorization_code = "paste_code_from_redirect_here"
token_data = oauth_client.exchange_code_for_token(authorization_code)

print(f"Access Token: {token_data['access_token']}")
print(f"Refresh Token: {token_data['refresh_token']}")
print(f"Expires In: {token_data['expires_in']} seconds")

# Save these tokens securely!
```

### Save Tokens Securely

For production, store tokens in:
- **AWS Secrets Manager** (recommended for Lambda)
- **Environment variables** (for local development)
- **Encrypted database** (for multi-user apps)

**Never commit tokens to version control!**

## Step 4: Fetch Run Data

Once you have an access token, you can fetch your running data.

### Example: Fetch Latest Runs

```python
from datetime import date
from src.shared.smashrun import SmashRunAPIClient
from src.shared.duckdb_ops import DuckDBManager, RunRepository

# Use access token from OAuth flow
access_token = "your_access_token_here"

# Create API client
with SmashRunAPIClient(access_token=access_token) as api_client:
    # Fetch user info
    user_info = api_client.get_user_info()
    print(f"Authenticated as: {user_info['userName']}")

    # Fetch latest 10 runs
    activities = api_client.get_activities(page=0, count=10)
    print(f"Found {len(activities)} activities")

    # Fetch all runs since a specific date
    since_date = date(2024, 1, 1)
    all_activities = api_client.get_all_activities_since(since_date)
    print(f"Total runs since {since_date}: {len(all_activities)}")

    # Parse and store in database
    db_manager = DuckDBManager("./data/runs.duckdb")
    db_manager.initialize_schema()

    with db_manager as conn:
        repo = RunRepository(conn)

        for activity_data in all_activities:
            # Parse into Activity model
            activity = api_client.parse_activity(activity_data)

            # Store in DuckDB
            repo.upsert_run(activity)
            print(f"Stored run: {activity.activity_id} - {activity.distance_miles:.2f} mi")
```

### Example: Fetch Specific Date Range

```python
from datetime import date

with SmashRunAPIClient(access_token=access_token) as api_client:
    # Fetch October 2024 runs
    october_runs = api_client.get_activities(
        page=0,
        count=100,
        since=date(2024, 10, 1),
        until=date(2024, 10, 31)
    )

    for run_data in october_runs:
        run = api_client.parse_activity(run_data)
        print(f"{run.start_date_time_local.date()}: {run.distance_miles:.2f} mi")
```

## Step 5: Refresh Tokens

Access tokens expire after 12 weeks. Use refresh tokens to get new access tokens without re-authorizing.

### Refresh Token Example

```python
from src.shared.smashrun import SmashRunOAuthClient

oauth_client = SmashRunOAuthClient(
    client_id=settings.smashrun_client_id,
    client_secret=settings.smashrun_client_secret,
    redirect_uri=settings.smashrun_redirect_uri,
)

# Use saved refresh token
refresh_token = "your_saved_refresh_token"

# Get new access token
new_token_data = oauth_client.refresh_access_token(refresh_token)

print(f"New Access Token: {new_token_data['access_token']}")
print(f"New Refresh Token: {new_token_data['refresh_token']}")  # May be same or new

# Update stored tokens
```

### When to Refresh

Refresh tokens when:
- Access token expires (12 weeks)
- API returns 401 Unauthorized
- Before scheduled daily sync (proactive)

## 🔐 Security Best Practices

### 1. Never Commit Secrets

```bash
# .gitignore already includes:
.env
*.tfvars
secrets.json
```

### 2. Use AWS Secrets Manager (Production)

```python
import boto3
import json

def get_smashrun_tokens():
    """Fetch tokens from AWS Secrets Manager."""
    client = boto3.client('secretsmanager', region_name='us-east-2')
    response = client.get_secret_value(SecretId='myrunstreak/smashrun/tokens')
    return json.loads(response['SecretString'])

def update_smashrun_tokens(access_token, refresh_token):
    """Update tokens in AWS Secrets Manager."""
    client = boto3.client('secretsmanager', region_name='us-east-2')
    client.update_secret(
        SecretId='myrunstreak/smashrun/tokens',
        SecretString=json.dumps({
            'access_token': access_token,
            'refresh_token': refresh_token
        })
    )
```

### 3. Rotate Tokens Regularly

Even though refresh tokens don't expire, rotate them periodically:
- Re-authorize every 6 months
- After any security incidents
- If tokens may have been compromised

## 🚀 Complete Sync Script

Here's a complete script to sync all your SmashRun data:

```python
#!/usr/bin/env python3
"""Sync SmashRun data to local DuckDB database."""

import logging
from datetime import date

from src.shared.config import get_settings
from src.shared.smashrun import SmashRunAPIClient
from src.shared.duckdb_ops import DuckDBManager, RunRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sync_smashrun_data(access_token: str, since: date | None = None):
    """
    Sync SmashRun running data to local database.

    Args:
        access_token: Valid SmashRun access token
        since: Fetch runs on or after this date (None = all time)
    """
    settings = get_settings()

    # Initialize database
    db_manager = DuckDBManager(settings.duckdb_path)
    db_manager.initialize_schema()

    # Fetch and store runs
    with SmashRunAPIClient(access_token=access_token) as api_client:
        logger.info("Fetching user info...")
        user_info = api_client.get_user_info()
        logger.info(f"Authenticated as: {user_info['userName']}")

        # Fetch all activities
        logger.info(f"Fetching activities since {since or 'beginning'}...")
        if since:
            activities = api_client.get_all_activities_since(since)
        else:
            # Fetch all activities (paginated)
            activities = []
            page = 0
            while True:
                batch = api_client.get_activities(page=page, count=100)
                if not batch:
                    break
                activities.extend(batch)
                page += 1

        logger.info(f"Found {len(activities)} activities")

        # Store in database
        with db_manager as conn:
            repo = RunRepository(conn)

            for activity_data in activities:
                try:
                    activity = api_client.parse_activity(activity_data)
                    repo.upsert_run(activity)
                    logger.info(
                        f"✓ Stored: {activity.start_date_time_local.date()} - "
                        f"{activity.distance_miles:.2f} mi"
                    )
                except Exception as e:
                    logger.error(f"Failed to process activity: {e}")
                    continue

        logger.info(f"Successfully synced {len(activities)} runs!")

if __name__ == "__main__":
    # Load access token from environment or AWS Secrets Manager
    settings = get_settings()
    access_token = input("Enter SmashRun access token: ")

    # Sync all data
    sync_smashrun_data(access_token)

    # Or sync only recent data
    # sync_smashrun_data(access_token, since=date(2024, 1, 1))
```

Save as `scripts/sync_smashrun.py` and run:

```bash
chmod +x scripts/sync_smashrun.py
./scripts/sync_smashrun.py
```

## 📊 Rate Limiting

SmashRun enforces rate limits:
- **250 requests per hour** for user-level tokens
- **No rate limit** for batch operations (within reason)

### Handle Rate Limits

```python
import time
from httpx import HTTPStatusError

try:
    activities = api_client.get_activities(page=0, count=100)
except HTTPStatusError as e:
    if e.response.status_code == 429:  # Too Many Requests
        retry_after = int(e.response.headers.get('Retry-After', 3600))
        logger.warning(f"Rate limited. Retry after {retry_after} seconds")
        time.sleep(retry_after)
        # Retry request
        activities = api_client.get_activities(page=0, count=100)
```

## 🔧 Troubleshooting

### Invalid Grant Error

If token exchange fails with "invalid_grant":
- Check that authorization code hasn't expired (use immediately)
- Verify redirect URI matches exactly
- Ensure client ID and secret are correct

### 401 Unauthorized

If API requests fail with 401:
- Access token may have expired (12 weeks)
- Refresh token or re-authorize
- Check token is being sent correctly in headers

### No Activities Returned

If `get_activities()` returns empty list:
- Verify you have runs in SmashRun
- Check date filters (since/until)
- Try fetching without filters first

## 📚 API Reference

### SmashRunOAuthClient

```python
oauth_client = SmashRunOAuthClient(
    client_id="your_client_id",
    client_secret="your_client_secret",
    redirect_uri="http://localhost:8000/callback",
    scope="read_activity"  # or "write_activity"
)

# Generate authorization URL
url = oauth_client.get_authorization_url(state="csrf_token")

# Exchange code for tokens
tokens = oauth_client.exchange_code_for_token("auth_code")

# Refresh access token
new_tokens = oauth_client.refresh_access_token("refresh_token")
```

### SmashRunAPIClient

```python
with SmashRunAPIClient(access_token="token") as api_client:
    # Get user info
    user = api_client.get_user_info()

    # Fetch activities
    runs = api_client.get_activities(page=0, count=50)

    # Fetch with date filter
    runs = api_client.get_activities(
        page=0,
        count=100,
        since=date(2024, 1, 1),
        until=date(2024, 12, 31)
    )

    # Get all activities since date (auto-pagination)
    all_runs = api_client.get_all_activities_since(date(2024, 1, 1))

    # Get specific run
    run = api_client.get_activity_by_id("activity_id")

    # Get latest run
    latest = api_client.get_latest_activity()

    # Parse to Activity model
    activity = api_client.parse_activity(run_data)
```

## 🎯 Next Steps

Now that you have OAuth working:

1. **Automate sync** - Create Lambda function for daily syncing
2. **Build API** - Expose streak/analytics endpoints
3. **Add scheduling** - Use EventBridge for daily triggers
4. **Deploy** - Push to AWS with Terraform

Ready to build the automated sync Lambda function?
