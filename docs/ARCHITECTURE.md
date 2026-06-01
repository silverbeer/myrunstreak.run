# MyRunStreak.run — Architecture

The platform runs entirely on **Linode Kubernetes Engine (LKE)**, packaged as a
Helm chart and delivered via ArgoCD GitOps. Data lives in **Supabase Postgres**.

> **History:** the original design was AWS-serverless (Lambda × 4, API Gateway,
> EventBridge, S3-hosted DuckDB, Secrets Manager). That stack was decommissioned
> in the LKE migration ("Phase C"). The only AWS left is the Terraform state
> backend and a single Secrets Manager secret pulled into the cluster by the
> External Secrets Operator. See `git log` for the migration commits.

## Overview

```
                         SmashRun API (OAuth)
                                 ▲
                                 │ fetch activities + goals
                   ┌─────────────┴─────────────┐
                   │   sync CronJob (14,17 UTC) │
                   └─────────────┬─────────────┘
                                 ▼
   Vue SPA ──HTTPS──► FastAPI backend ──► Supabase Postgres
 (myrunstreak.run)   (api.myrunstreak.run)      ▲
        ▲                   │   ▲                │
        │                   ▼   └── Redis cache ─┘
   stk CLI ───────────► (auth/sync/stats)
                                 │
            publish-status CronJob (*/15) ──► public status feed
```

Everything below the SmashRun box runs as pods in one LKE cluster, deployed by
the `helm/myrunstreak/` chart.

## Components

### Frontend — Vue 3 SPA
- Vue 3 + Vite + Tailwind + Pinia + vue-router, talks to Supabase Auth directly
  and to the backend for data.
- Built to static assets, served by nginx in the container (`/health` probe).
- Served at `myrunstreak.run` / `www.myrunstreak.run`; 2 replicas.

### Backend — FastAPI (`api.myrunstreak.run`)
- `app.py`: CORS, route mounting, `/health`.
- `routes/`: `stats` (`/stats/{overall,streaks,monthly,records,goals}`),
  `runs` (`/runs`, `/runs/recent`), `sync` (`POST /sync-user`),
  `auth_routes` (`/auth/{login-url,callback,store-tokens,...}` — backs the thin
  CLI and password-reset proxy).
- `auth.py`: Supabase JWT verification dependency (replaces the old API Gateway
  authorizer).
- `cache.py`: Redis client + `@cached` decorator + `invalidate_user()`.
- `src/shared/`: Supabase repositories, SmashRun client, Pydantic models —
  shared between the backend and the CLI.

### Database — Supabase Postgres
- Multi-user, multi-source schema with Row-Level Security. See
  [DATA_MODEL.md](DATA_MODEL.md).
- Schema changes are SQL migrations under `supabase/migrations/`, applied by the
  `supabase-migrations` workflow.

### Cache — Redis
- Caches heavy stats aggregations (TTL ~60s). Keys namespaced
  `mrs:<prefix>:<user_id>:<args>`; `invalidate_user()` clears a user's entries
  after a sync. Degrades gracefully when disabled/unreachable.

### Scheduled jobs — K8s CronJobs
- **sync** (`0 14,17 * * *` UTC) — `backend/jobs/sync_runs.py`: pulls new runs
  and goal progress for every enrolled user, recomputes stats.
- **publish-status** (`*/15 * * * *`) — `backend/jobs/publish_status.py`:
  publishes a public status feed (powers external embeds).

### Secrets
- A single AWS Secrets Manager secret, `myrunstreak-app-secrets`, is synced into
  a K8s `Secret` by the **External Secrets Operator** (`refreshInterval: 1h`).
  Pods read Supabase keys, the JWT secret, and SmashRun OAuth client creds from
  it. The ExternalSecret is ArgoCD-managed via the chart.

## Auth model

- **App users** authenticate with **Supabase Auth**; the backend verifies the
  JWT on each request (`auth.py`).
- **SmashRun** uses **OAuth**, handled **server-side** by the backend so the CLI
  stays a thin client. Per-user tokens live in `user_sources`
  (`access_token` / `refresh_token` / `token_expires_at`). See
  [SMASHRUN_OAUTH.md](SMASHRUN_OAUTH.md).

## Delivery (GitOps)

```
push to backend/** or frontend/**
        ↓  GitHub Actions (backend-deploy / frontend-deploy)
build image → push to GHCR → bump tag in helm/myrunstreak/values.yaml
        ↓  ArgoCD watches the chart
reconcile onto LKE
```

- Image tags are pinned in `helm/myrunstreak/values.yaml`
  (`image.tag` for frontend, `backend.image.tag` for backend). Automated tag
  bumps commit with `[skip ci]`.
- Supabase migrations apply via their own workflow on merge to `main`.
- See [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) and
  [TERRAFORM.md](TERRAFORM.md).

## What runs where

| Concern | Where |
|---------|-------|
| Web app, API, cache, cron | LKE pods (Helm chart) |
| Database | Supabase (managed Postgres) |
| Container images | GHCR |
| GitOps reconciliation | ArgoCD |
| CI (build/test/tag-bump) | GitHub Actions |
| App secret store | AWS Secrets Manager → External Secrets Operator |
| Terraform state | AWS S3 backend (only) |
