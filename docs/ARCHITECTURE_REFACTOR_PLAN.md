# Architecture Refactor Plan: Secure Thin-Client CLI

## Current State (Problems)

1. **CLI has too many responsibilities** - fetches from SmashRun, writes to Supabase
2. **Secrets scattered** - SmashRun credentials in .env, Supabase credentials in .env and Lambda env vars
3. **Lambda env vars expose secrets** - visible in AWS Console
4. **User OAuth tokens stored locally** - in `~/.config/stk/tokens.json`

## Target State

```
┌─────────┐     ┌─────────────┐     ┌────────┐     ┌──────────┐
│   CLI   │ ──► │ API Gateway │ ──► │ Lambda │ ──► │ SmashRun │
└─────────┘     └─────────────┘     └────────┘     └──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │ AWS Secrets Manager │
                              │  • SmashRun creds   │
                              │  • Supabase creds   │
                              └─────────────────────┘
                                         │
                                         ▼
                                   ┌──────────┐
                                   │ Supabase │
                                   │ • runs   │
                                   │ • users  │
                                   │ • tokens │
                                   └──────────┘
```

**CLI `.env` becomes:**
```
API_BASE_URL=https://xxx.execute-api.us-east-2.amazonaws.com/dev
```

That's it. One variable.

---

## Implementation Steps

### Phase 0: Custom Domain Setup

**Step 0.1: Create SSL certificate in ACM**

```bash
# Must be in us-east-1 for API Gateway
aws acm request-certificate \
  --domain-name api.myrunstreak.com \
  --validation-method DNS \
  --region us-east-1
```

Or for the root domain:
```bash
aws acm request-certificate \
  --domain-name myrunstreak.com \
  --subject-alternative-names "*.myrunstreak.com" \
  --validation-method DNS \
  --region us-east-1
```

**Step 0.2: Validate certificate**
- Add DNS validation records to your domain
- Wait for certificate to be issued (usually < 30 min)

**Step 0.3: Create custom domain in API Gateway**

```bash
aws apigateway create-domain-name \
  --domain-name api.myrunstreak.com \
  --regional-certificate-arn arn:aws:acm:us-east-1:xxx:certificate/xxx \
  --endpoint-configuration types=REGIONAL
```

**Step 0.4: Map API to custom domain**

```bash
aws apigateway create-base-path-mapping \
  --domain-name api.myrunstreak.com \
  --rest-api-id xxx \
  --stage dev
```

**Step 0.5: Update DNS**

Add CNAME or ALIAS record:
```
api.myrunstreak.com → d-xxx.execute-api.us-east-2.amazonaws.com
```

**Step 0.6: Update Terraform**

Add custom domain resources to manage via IaC.

**Result:**
```
API_BASE_URL=https://api.myrunstreak.com
```

This keeps `myrunstreak.com` available for a future web dashboard.

---

### Phase 1: Secrets Manager Setup

**Step 1.1: Create secrets in AWS Secrets Manager**

```bash
# SmashRun OAuth credentials
aws secretsmanager create-secret \
  --name myrunstreak/smashrun \
  --secret-string '{
    "client_id": "xxx",
    "client_secret": "xxx",
    "redirect_uri": "https://myrunstreak.com/callback"
  }'

# Supabase credentials
aws secretsmanager create-secret \
  --name myrunstreak/supabase \
  --secret-string '{
    "url": "https://xxx.supabase.co",
    "service_role_key": "xxx"
  }'
```

**Step 1.2: Update Terraform**

- Add Secrets Manager resources (or import existing)
- Grant Lambda IAM role `secretsmanager:GetSecretValue` permission
- Remove secrets from Lambda environment variables

**Step 1.3: Create secrets utility module**

```python
# src/shared/secrets.py
import boto3
import json
from functools import lru_cache

@lru_cache
def get_secret(secret_name: str) -> dict:
    """Fetch secret from AWS Secrets Manager (cached)."""
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

def get_smashrun_credentials() -> dict:
    return get_secret('myrunstreak/smashrun')

def get_supabase_credentials() -> dict:
    return get_secret('myrunstreak/supabase')
```

---

### Phase 2: Store User OAuth Tokens in Supabase

**Step 2.1: Add columns to user_sources table**

```sql
ALTER TABLE user_sources ADD COLUMN IF NOT EXISTS
  access_token TEXT,
  refresh_token TEXT,
  token_expires_at TIMESTAMPTZ;
```

**Step 2.2: Create token management functions**

```python
# src/shared/supabase_ops/token_repository.py
class TokenRepository:
    def get_user_tokens(self, user_id: UUID) -> dict | None:
        """Get OAuth tokens for user's SmashRun source."""

    def save_user_tokens(self, user_id: UUID, tokens: dict) -> None:
        """Save/update OAuth tokens."""

    def refresh_if_expired(self, user_id: UUID) -> str:
        """Refresh token if expired, return valid access token."""
```

---

### Phase 3: New Lambda Sync Endpoint

**Step 3.1: Add POST /sync endpoint**

```python
# src/lambdas/query_runs/handler.py

@app.post("/sync")
def sync_runs() -> dict:
    """
    Sync runs from SmashRun to Supabase.

    Body:
        since: Optional date string (YYYY-MM-DD)
        until: Optional date string
        full: Optional bool for full sync

    Flow:
        1. Get user_id from request (API key or JWT)
        2. Get user's OAuth tokens from Supabase
        3. Refresh token if expired
        4. Fetch runs from SmashRun API
        5. Store runs to Supabase
        6. Return summary
    """
```

**Step 3.2: Update Lambda to use Secrets Manager**

- Remove hardcoded env var reads
- Use `get_supabase_credentials()` for Supabase client
- Use `get_smashrun_credentials()` for SmashRun OAuth

---

### Phase 4: Refactor CLI to Thin Client

**Step 4.1: Simplify sync command**

```python
# src/cli/commands/sync.py

def sync_runs(since: str | None, until: str | None, full: bool):
    """Sync runs from SmashRun."""

    # Just call the API
    result = api.request("sync", method="POST", json={
        "since": since,
        "until": until,
        "full": full
    })

    display.display_sync_result(result)
```

**Step 4.2: Simplify auth command**

The OAuth flow still needs to happen locally (browser redirect), but tokens get sent to API:

```python
# src/cli/commands/auth.py

def login():
    """Authenticate with SmashRun."""

    # 1. Get OAuth URL from API (it has the client_id)
    auth_info = api.request("auth/oauth-url")

    # 2. Open browser, get callback code
    code = do_oauth_flow(auth_info["url"])

    # 3. Send code to API to exchange for tokens
    result = api.request("auth/callback", method="POST", json={"code": code})

    # 4. Store user_id locally for API calls
    save_config({"user_id": result["user_id"]})
```

**Step 4.3: Remove Supabase and SmashRun dependencies from CLI**

- Remove `supabase` from CLI dependencies
- Remove `shared.smashrun` imports from CLI
- Remove `shared.supabase_*` imports from CLI
- CLI only needs: `httpx`, `typer`, `rich`

**Step 4.4: Update CLI config**

`~/.config/stk/config.json`:
```json
{
  "api_base_url": "https://xxx.execute-api.us-east-2.amazonaws.com/dev",
  "user_id": "16eb502d-7fc0-4fce-9107-9931df747e28"
}
```

No more `tokens.json` locally.

---

### Phase 5: Add Auth Endpoints to Lambda

**Step 5.1: OAuth URL endpoint**

```python
@app.get("/auth/oauth-url")
def get_oauth_url() -> dict:
    """Get SmashRun OAuth URL for CLI to open."""
    creds = get_smashrun_credentials()
    # Build OAuth URL
    return {"url": oauth_url}
```

**Step 5.2: Callback endpoint**

```python
@app.post("/auth/callback")
def handle_callback(code: str) -> dict:
    """Exchange OAuth code for tokens and store."""
    # 1. Exchange code for tokens using SmashRun credentials
    # 2. Get user info from SmashRun
    # 3. Create/update user in Supabase
    # 4. Store tokens in user_sources
    # 5. Return user_id
```

---

### Phase 6: Testing

**Step 6.1: Local testing**
- Test Lambda with SAM local or direct invocation
- Test Secrets Manager access
- Test token refresh flow

**Step 6.2: Integration testing**
- Full OAuth flow
- Sync with various date ranges
- Token expiration and refresh

**Step 6.3: CLI testing**
- All commands work with only API_BASE_URL
- Error handling for API failures

---

### Phase 7: Cleanup

**Step 7.1: Remove from `.env`**
- SMASHRUN_CLIENT_ID
- SMASHRUN_CLIENT_SECRET
- SMASHRUN_REDIRECT_URI
- SUPABASE_URL
- SUPABASE_KEY

**Step 7.2: Remove from Lambda env vars**
- SUPABASE_URL
- SUPABASE_KEY

**Step 7.3: Update documentation**
- README with new setup instructions
- Only `API_BASE_URL` needed

---

## Migration Path for Existing Users

1. Run new `stk auth login` to migrate tokens to Supabase
2. Delete `~/.config/stk/tokens.json`
3. Update `.env` to only have `API_BASE_URL`
4. Continue using CLI as normal

---

## Security Benefits

1. **No secrets on dev machines** - only API URL
2. **Secrets encrypted at rest** - Secrets Manager uses KMS
3. **Access audited** - CloudTrail logs all secret access
4. **Rotation possible** - can rotate secrets without redeploying
5. **IAM-controlled** - only Lambda role can access secrets
6. **User tokens server-side** - not stored in local files

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Secrets Manager adds latency | Cache secrets after cold start |
| More complex OAuth flow | Clear error messages, retry logic |
| Breaking change for existing users | Migration command, clear docs |
| Lambda cold starts slower | Keep Lambda warm, optimize imports |

---

## Estimated Effort

| Phase | Effort |
|-------|--------|
| 0. Custom domain setup | 1-2 hours |
| 1. Secrets Manager setup | 1-2 hours |
| 2. Token storage in Supabase | 1-2 hours |
| 3. New sync endpoint | 2-3 hours |
| 4. Refactor CLI | 2-3 hours |
| 5. Auth endpoints | 2-3 hours |
| 6. Testing | 2-3 hours |
| 7. Cleanup & docs | 1 hour |
| **Total** | **13-19 hours** |

---

## Questions for Review

1. Should we support multiple SmashRun accounts per user?
2. Do we need API key auth or JWT for the API?
3. Should the CLI store user_id or derive it from an API key?
4. Do we want to keep local sync as a fallback during migration?

---

## Approval

- [ ] Architecture approved
- [ ] Security approach approved
- [ ] Migration path approved
- [ ] Ready to implement
