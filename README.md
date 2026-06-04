# MyRunStreak.run

A multi-user running analytics platform that tracks daily running streaks from
SmashRun. FastAPI backend + Vue 3 web app, running on Linode Kubernetes (LKE)
with Supabase Postgres.

## Overview

MyRunStreak connects to the SmashRun API via OAuth, syncs your runs into Supabase
Postgres, and surfaces streaks, stats, and goal progress through a web dashboard
and a thin-client CLI. Sync runs on a schedule; a public status feed powers
embeds on other sites.

## Architecture

| Component | Technology |
|-----------|------------|
| Frontend | Vue 3 + Vite + Tailwind + Pinia (`myrunstreak.run`) |
| Backend API | FastAPI (`api.myrunstreak.run`) |
| Database | Supabase Postgres (RLS, SQL migrations) |
| Cache | Redis (stats endpoints) |
| Auth | Supabase Auth (JWT); SmashRun OAuth for data sync |
| Runtime | Linode Kubernetes Engine (LKE) |
| Packaging | Helm chart (`helm/myrunstreak/`) |
| Delivery | GitHub Actions → GHCR images → ArgoCD GitOps |
| Scheduling | K8s CronJobs (daily sync, status publish) |
| Secrets | AWS Secrets Manager → External Secrets Operator → K8s Secret |

AWS is used only for the Terraform state backend and a single Secrets Manager
secret that the External Secrets Operator pulls into the cluster. All
application infrastructure runs on LKE. (The original AWS Lambda + API Gateway
stack was decommissioned — see `docs/ARCHITECTURE.md`.)

```
SmashRun API ──OAuth──> sync CronJob ──> Supabase Postgres
                                              │
                       FastAPI backend ◄──────┘   (Redis-cached)
                              ▲
              ┌───────────────┼────────────────┐
        Vue web app       stk CLI        public status feed
```

## Repo layout

```
myrunstreak.run/
├── backend/                # FastAPI app (see backend/README.md)
│   ├── app.py              # entry — CORS, routes, /health
│   ├── routes/             # stats, runs, sync, auth_routes
│   ├── jobs/               # CronJob entrypoints (sync_runs, publish_status)
│   ├── goals.py            # SmashRun goal-progress presentation
│   └── streaks.py
├── frontend/               # Vue 3 + Vite SPA (nginx-served)
│   └── src/{views,components,composables,stores,router}
├── src/
│   ├── cli/                # stk — thin-client CLI (auth/sync/stats via backend)
│   └── shared/             # Supabase ops, SmashRun client, Pydantic models
├── helm/myrunstreak/       # Helm chart (backend, frontend, redis, cronjobs)
├── supabase/migrations/    # Postgres schema migrations
├── terraform/              # state backend + ASM secret only (see docs/TERRAFORM.md)
└── docs/
```

## Quick start (local)

```bash
# Backend
uv sync --all-extras
supabase start                                   # local Postgres
uv run uvicorn backend.app:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

See [QUICKSTART.md](QUICKSTART.md) and [docs/TESTING.md](docs/TESTING.md).

### Local Supabase port convention (SB-113)

Each silverbeer repo gets its own 100-port block so local stacks run side-by-side:

| Repo | Block | API | DB | Studio |
|------|-------|-----|----|--------|
| myrunstreak (this repo) | 543xx (defaults) | 54321 | 54322 | 54323 |
| missing-table | 553xx | 55321 | 55322 | 55323 |
| *(next repo)* | 563xx | 56321 | 56322 | 56323 |

## CLI (`stk`)

`stk` is a thin client — it authenticates and syncs through the backend, which
holds the SmashRun OAuth credentials server-side.

```bash
stk auth login      # authenticate
stk auth status     # check login status
stk sync            # sync recent runs
stk stats           # overall statistics
stk runs            # list recent runs
stk streak          # current streak
```

## Tech stack

- **Backend**: Python 3.12, FastAPI, UV, Pydantic v2, Supabase, Redis
- **Frontend**: Vue 3, Vite, Tailwind, Pinia, vue-router, supabase-js, Vitest
- **Infra**: LKE, Helm, ArgoCD, GitHub Actions, GHCR, External Secrets
- **Data**: Supabase Postgres (migrations under `supabase/migrations/`)

## Development

```bash
uv sync --all-extras
uv run pytest                         # shared/CLI tests
uv run --project backend pytest backend/tests/
cd frontend && npm test               # vitest

uv run ruff check .                   # lint
uv run ruff format .                  # format
uv run mypy src/                      # type check
```

## Deployment

CI builds backend/frontend images to GHCR on push, then bumps the image tag in
`helm/myrunstreak/values.yaml`; ArgoCD reconciles the chart onto LKE. Supabase
migrations apply via the `supabase-migrations` workflow.

See [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Data Model](docs/DATA_MODEL.md)
- [Testing](docs/TESTING.md)
- [SmashRun OAuth](docs/SMASHRUN_OAUTH.md)
- [Terraform (state backend only)](docs/TERRAFORM.md)
- [Units](docs/UNITS.md)
- [Goals & Multi-Metric Tracking](docs/GOALS_TRACKING.md) *(planned)*
- [Sources, BYOK & Import](docs/SOURCES_AND_IMPORT.md) *(planned)*
- [Gear & Device Tracking](docs/GEAR_TRACKING.md) *(planned)*
- [Social & Community](docs/SOCIAL.md) *(planned)*

## License

MIT
