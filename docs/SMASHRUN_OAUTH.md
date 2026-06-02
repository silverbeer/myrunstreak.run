# SmashRun OAuth Integration

How MyRunStreak authenticates with SmashRun and syncs run data. OAuth is handled
**server-side by the backend** so the web app and the `stk` CLI stay thin
clients — they never see the SmashRun client secret.

## Model

- The **app** holds one SmashRun OAuth application's `client_id` /
  `client_secret` (from env / the app secret), not per-user.
- Each **user** authorizes their own SmashRun account. Their tokens are stored
  per-user in `user_sources` (`access_token`, `refresh_token`,
  `token_expires_at`) via `TokenRepository`. No AWS Secrets Manager, no DuckDB.
- The sync CronJob and API read tokens from `user_sources`, refreshing as needed.

```
client (web / stk) ──► backend /auth/login-url ──► SmashRun authorize page
SmashRun ──redirect──► backend /auth/callback ──► exchange code ──► user_sources
sync CronJob ──► TokenRepository.get_valid(...) ──► SmashRunAPIClient ──► runs
```

## Backend endpoints (`backend/routes/auth_routes.py`)

| Endpoint | Purpose |
|----------|---------|
| `GET  /auth/login-url` | Build the SmashRun authorization URL (with state) |
| `POST /auth/callback` | Exchange the authorization code for tokens, store them |
| `POST /auth/store-tokens` | Persist tokens for the user's SmashRun source |
| `POST /auth/{signup,login,refresh}` | Supabase Auth for app users |
| `POST /auth/{forgot,reset}-password` | Password-reset proxy |

The `stk` CLI drives `login-url` → opens the browser → `callback`/`store-tokens`
against the backend.

## Create a SmashRun API application

1. https://smashrun.com/settings/api → log in → **Create New Application**.
2. Name it (e.g. *MyRunStreak*), set the **Redirect URI** to the backend
   callback (local dev: `http://localhost:8000/auth/callback`; prod: the
   `api.myrunstreak.run` equivalent).
3. Copy **Client ID** and **Client Secret** into the backend config
   (`backend/.env` locally; the app secret in production). Never commit them.

## Token lifecycle

- SmashRun access **and** refresh tokens both last ~12 weeks (~84 days).
- `TokenRepository` refreshes at roughly the **halfway point** (~6 weeks) so both
  tokens roll forward together — waiting until expiry risks losing both.
- If a source is offline > 12 weeks (both tokens dead) or after a 401 following a
  long outage, the user must re-authorize through the `/auth/login-url` flow.

## Client classes (`src/shared/smashrun/`)

```python
# oauth.py
oauth = SmashRunOAuthClient(client_id=..., client_secret=..., redirect_uri=...)
url    = oauth.get_authorization_url(state="csrf_token")
tokens = oauth.exchange_code_for_token("auth_code")
fresh  = oauth.refresh_access_token("refresh_token")

# client.py
with SmashRunAPIClient(access_token=token) as api:
    api.get_user_info()
    api.get_activities(page=0, count=50, since=date(2024, 1, 1))
    api.get_all_activities_since(date(2024, 1, 1))   # auto-paginates
    api.parse_activity(raw)                          # -> Activity model
```

Parsed `Activity` models are upserted into Supabase via
`src/shared/supabase_ops` (see [DATA_MODEL.md](DATA_MODEL.md)).

## Rate limiting

SmashRun allows ~250 requests/hour per user token. On `429`, honor the
`Retry-After` header and back off. The sync job paginates in batches to stay
within budget.

## Troubleshooting

- **`invalid_grant` on exchange** — authorization code expired (use immediately),
  or the redirect URI doesn't match the registered one exactly.
- **`401 Unauthorized`** — access token expired; refresh, or re-authorize if the
  refresh token is also dead.
- **Empty activity list** — confirm runs exist and check `since`/`until` filters.
