# myrunstreak backend

FastAPI backend that replaces the AWS Lambda stack. Deployed to LKE via Helm/ArgoCD,
mirroring the missing-table.com pattern.

## What's here

```
backend/
├── app.py              FastAPI entry — CORS middleware, route mounting, /health
├── auth.py             Supabase JWT verification dependency (replaces API GW authorizer)
├── cache.py            Redis client + @cached decorator + invalidate_user()
├── config.py           pydantic-settings env-var config
├── routes/
│   ├── stats.py        /stats/{overall,streaks,monthly,records}
│   ├── runs.py         /runs, /runs/recent
│   ├── sync.py         POST /sync-user (also exposes run_user_sync used by CronJob)
│   └── auth_routes.py  /auth/{login-url,callback,store-tokens}
├── jobs/
│   └── sync_runs.py    K8s CronJob entry point: syncs every enrolled user
├── tests/              pytest, fakeredis for cache tests
├── Dockerfile          python:3.12-slim + uv
└── pyproject.toml      uv-managed deps
```

`src/shared/` (Supabase ops, SmashRun client, models) is lifted into the image
unchanged. It will move under `backend/shared/` once the Lambda code path is
removed in the LKE migration's Phase C.

## Local dev

```bash
cd backend
uv sync --all-extras
cp .env.example .env  # fill in Supabase URL/key/jwt_secret
uv run uvicorn backend.app:app --reload --port 8000
```

## Tests

```bash
uv run --project backend python -m pytest backend/tests/
```

21 tests cover auth (10), cache (8), and FastAPI smoke (4).

## Caching

`@cached(ttl=60, key_prefix="stats:overall")` wraps the heavy aggregations.
Keys are namespaced `mrs:<prefix>:<user_id>:<args>` so `invalidate_user()`
called after a sync clears just that user's entries.

When `CACHE_ENABLED=false` or Redis is unreachable, the decorator falls
through to the wrapped function — no behavior change.
