# Local Development

How to run MyRunStreak on your machine against a local Supabase stack, with a
clean set of seeded users.

## Prerequisites

- **Docker Desktop** (running) — local Supabase runs in containers.
- **[uv](https://github.com/astral-sh/uv)** — Python deps + commands.
- **Node + npm** — the Vue frontend.
- **[Supabase CLI](https://supabase.com/docs/guides/cli)** — local Postgres/Auth.
- (Optional) **1Password CLI (`op`)** + `jt` — only for prod secrets / syncing
  prod users; not needed for pure local work.

## Environment files

`./switch-env.sh {local|prod}` repoints `.env` (and `frontend/.env`) at
`.env.<env>`. These files are gitignored — create them once.

### `.env.local`

Local Supabase uses the well-known demo keys. Minimum working file:

```bash
ENVIRONMENT=dev
LOG_LEVEL=INFO
CACHE_ENABLED=false

SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=<local anon key from `supabase status`>
SUPABASE_SERVICE_ROLE_KEY=<local service_role key from `supabase status`>
# REQUIRED: the backend's SupabaseSettings reads SUPABASE_KEY (service role).
# Without it every DB route 500s locally. Set it to the same service_role key.
SUPABASE_KEY=<same as SUPABASE_SERVICE_ROLE_KEY>
SUPABASE_JWT_SECRET=super-secret-jwt-token-with-at-least-32-characters-long
```

> ⚠️ **`SUPABASE_KEY` is required.** The backend (`src/shared/supabase_client.py`)
> loads `SUPABASE_KEY`; if it's missing, `SupabaseSettings` fails to validate and
> every DB-backed route returns 500 (health still returns 200, which is
> misleading). `.env.example` already includes it — don't drop it from
> `.env.local`.

### `.env.prod`

Copy `.env.example` and fill with the real cloud keys (or resolve via 1Password
with `jt secrets run`).

## Running the stack

```bash
./switch-env.sh local            # point env at local Supabase
./myrunstreak.sh start --watch   # local Supabase + backend (:8000) + frontend (:5174)
./myrunstreak.sh status          # what's up + active env
./myrunstreak.sh logs            # snapshot of backend/frontend logs
./myrunstreak.sh stop            # stop backend + frontend
```

The frontend serves at **http://localhost:5174** (Vite binds IPv6 — use
`localhost`, not `127.0.0.1`). Backend at http://localhost:8000.

## Seed local users

After the stack is up (and after any `db reset`), seed a clean, memorable set of
dev users:

```bash
eval "$(supabase status -o env | sed 's/^/export SB_/')"
SUPABASE_URL="$SB_API_URL" SERVICE_KEY="$SB_SERVICE_ROLE_KEY" \
  uv run python scripts/seed_local_users.py
```

The script is **idempotent** (rerun anytime) and **local-only** (it refuses to
run against a non-local Supabase URL). It produces:

| Email | Password | Role |
|-------|----------|------|
| `admin@test.local` | `admin123` | admin |
| `coach@test.local` | `coach123` | coach — coaches both athletes below |
| `a1@test.local` | `a12345` | athlete "Athlete One" (logs in as self) |
| `a2@test.local` | `a12345` | athlete "Athlete Two" (logs in as self) |

Athlete passwords are `a12345` because Supabase enforces a **6-character minimum**
(it ignores a lower `minimum_password_length` in `supabase/config.toml`).

The coach↔athlete links + `linked_user_id` are wired so the **Coach** tab,
act-as, and athlete-self-login all work immediately. Any `silverbeer.io@gmail.com`
user (from `jt supabase sync-users`) is left untouched; ad-hoc throwaway users
are purged.

Log in at http://localhost:5174 with any of the above.

## Database

```bash
./myrunstreak.sh db status    # is local Supabase up
./myrunstreak.sh db reset     # wipe local DB + re-apply all migrations (destructive, local only)
supabase migration up --local # apply pending migrations without wiping
```

After a `db reset`, re-run the seed script above.

> Prod migrations are **not** applied by these scripts — they ship via the
> `.github/workflows/supabase-migrations.yml` workflow on merge to `main`.

## Port convention (SB-113)

Each silverbeer repo gets its own 100-port block so local stacks coexist:

| Repo | API | DB | Studio |
|------|-----|----|--------|
| myrunstreak (this repo) | 54321 | 54322 | 54323 |
| missing-table | 55321 | 55322 | 55323 |

## See also

- [README](../README.md) — Quick start
- [docs/TESTING.md](TESTING.md) — running the test suites
- [docs/SUPABASE_MIGRATION.md](SUPABASE_MIGRATION.md) — schema migration notes
