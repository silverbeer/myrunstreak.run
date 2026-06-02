# Testing Guide

Three suites: shared/CLI Python tests, backend Python tests, and frontend Vue
tests. A local Supabase instance provides Postgres for anything touching the DB.

## Local database (Supabase)

```bash
supabase start          # local Postgres + applies migrations
supabase status         # shows API URL (54321) and DB URL (54322)
supabase db reset       # re-apply migrations from scratch
```

To work against a copy of production data locally:

```bash
make restore-prod       # scripts/restore_prod_to_local.sh
```

## Python tests

```bash
# Shared models, SmashRun client + OAuth  (tests/)
uv run pytest

# Backend: app, auth, cache, stats, streaks, goals, sync, publish-status
uv run --project backend python -m pytest backend/tests/ -v
```

What's covered:
- **`tests/`** — Pydantic models, SmashRun API client, SmashRun OAuth.
- **`backend/tests/`** — FastAPI smoke (`test_app`), JWT auth (`test_auth`,
  `test_auth_routes`), Redis cache with fakeredis (`test_cache`), stats &
  streaks, the goals module/repository/endpoint, sync, publish-status, secrets.

## Frontend tests

```bash
cd frontend
npm run type-check      # vue-tsc
npm test                # vitest run
npm run build           # production build must succeed
```

Component/composable/view tests live under `frontend/src/**/__tests__/`
(e.g. `GoalsCard`, `StatCard`, `useSync`, `useUserPreferences`,
`ResetPasswordView`).

## Code quality

```bash
uv run ruff check .             # lint
uv run ruff format --check .    # format check
uv run mypy src/                # type check
```

## What CI runs

- **`backend-test`** (PR/push touching `backend/**`, `src/shared/**`):
  `ruff check backend/` + `pytest backend/tests/ -v`.
- **`frontend-test`** (PR/push touching `frontend/**`): `npm ci`,
  `npm run type-check`, `npm test`, `npm run build`.
- **`supabase-migrations`** (PR/push touching `supabase/migrations/**`):
  validates/applies migrations.

Match CI locally before opening a PR: run the relevant suite(s) above.

## Manual API check

```bash
# backend running locally on :8000
curl localhost:8000/health
curl "localhost:8000/stats/overall?user_id=<uuid>"
```

## Related

- [QUICKSTART.md](../QUICKSTART.md) — get everything running locally
- [SUPABASE_MIGRATION.md](SUPABASE_MIGRATION.md) — DuckDB→Supabase history
- [DATA_MODEL.md](DATA_MODEL.md) — schema under test
