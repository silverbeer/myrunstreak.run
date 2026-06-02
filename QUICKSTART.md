# MyRunStreak.run — Quick Start

Get the backend, frontend, and a local database running for development.

## Prerequisites

- [ ] Python 3.12+ and [UV](https://github.com/astral-sh/uv)
      (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [ ] Node.js 20+ (for the Vue frontend)
- [ ] [Supabase CLI](https://supabase.com/docs/guides/cli) (local Postgres)
- [ ] Docker (Supabase CLI runs Postgres in containers)
- [ ] SmashRun API credentials (Client ID & Secret) from
      https://smashrun.com/settings/api — only needed to exercise live sync

## 1. Install dependencies

```bash
uv sync --all-extras          # Python: backend, CLI, shared
cd frontend && npm install && cd ..
```

## 2. Start the local database

```bash
supabase start                # spins up local Postgres + applies migrations
```

Note the printed API URL, anon key, and JWT secret — you'll need them for `.env`.

## 3. Run the backend

```bash
cp backend/.env.example backend/.env     # fill in Supabase URL / key / jwt_secret
uv run uvicorn backend.app:app --reload --port 8000
# health check
curl localhost:8000/health
```

## 4. Run the frontend

```bash
cd frontend
cp .env.example .env          # point at the backend + Supabase (if present)
npm run dev                   # Vite dev server
```

## 5. Verify

```bash
uv run pytest                              # shared / CLI tests
uv run --project backend pytest backend/tests/
cd frontend && npm test                    # vitest

uv run ruff check . && uv run ruff format --check .
uv run mypy src/
```

See [docs/TESTING.md](docs/TESTING.md) for the full testing guide.

## CLI (`stk`)

`stk` is a thin client that authenticates and syncs through the backend.

```bash
stk auth login        # authenticate via the backend
stk auth status
stk sync              # sync recent runs
stk stats             # overall statistics
```

## Live SmashRun sync (optional)

SmashRun OAuth client credentials are held **server-side** by the backend (in
local dev, via `backend/.env`; in production, from the app secret). Connect your
SmashRun account through the auth flow, then run a sync. See
[docs/SMASHRUN_OAUTH.md](docs/SMASHRUN_OAUTH.md).

## Make targets

```bash
make install      # uv sync --all-extras
make test         # pytest
make lint         # ruff check
make format       # ruff format
make type-check   # mypy
```

> The `*-tf` Make targets manage only the Terraform **state backend** and the
> app secret — not application infrastructure, which is deployed by Helm/ArgoCD
> onto LKE. See [docs/TERRAFORM.md](docs/TERRAFORM.md).

## Security reminders

🔒 Never commit `.env` files or `*.tfstate`. They're already in `.gitignore`.

## Help

- [README.md](README.md) — overview
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — how it all fits together
- [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md) — deploy
