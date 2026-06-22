---
name: dev-env
description: >-
  Drive the MyRunStreak local dev environment from chat via ./switch-env.sh and
  ./myrunstreak.sh. Use when the user wants to start/stop/restart the local app,
  check what's running, switch between local and prod env, reset or check the
  local database, or view backend/frontend logs — e.g. "start the app", "run it
  locally", "switch to local", "reset the local db", "what's running",
  "restart the backend", "show me the logs", "stop the servers".
---

# Dev environment — run the local stack from chat

Two scripts at the repo root manage everything; this skill maps the user's
request to them. Always run from the repo root.

## The tools
- **`./switch-env.sh {local|prod|status}`** — repoints `.env` (+ `frontend/.env`)
  at `.env.<env>`. `local` = local Supabase (`127.0.0.1:54321`); `prod` = the
  live cloud DB. State in `.mrs-config`.
- **`./myrunstreak.sh {start [--watch]|stop|restart|status|logs|tail|db}`** —
  backend (`:8000`) + frontend (`:5174`); `db` wraps `supabase start|stop|db
  reset|status`.

## Map requests → commands
| User says | Run |
|---|---|
| "what's running" / "status" | `./myrunstreak.sh status` |
| "start the app" / "run locally" | `./switch-env.sh local` then `./myrunstreak.sh start --watch` |
| "stop" / "stop the servers" | `./myrunstreak.sh stop` |
| "restart" / "restart backend" | `./myrunstreak.sh restart --watch` |
| "switch to local" / "use local db" | `./switch-env.sh local` (then offer restart) |
| "switch to prod" / "use the live db" | **confirm first**, then `./switch-env.sh prod` |
| "reset the local db" / "re-apply migrations" | **confirm**, then `./myrunstreak.sh db reset` |
| "start/stop the database" | `./myrunstreak.sh db up` / `db down` |
| "db status" / "is supabase up" | `./myrunstreak.sh db status` |
| "show logs" | `./myrunstreak.sh logs` (don't run `tail` — it blocks) |

## Always
- **Before any local-stack op (`start` when env=local, `db up`, `db reset`),
  verify Docker is running:** `docker info` (or the script's own
  `require_docker` gate handles it). If Docker is down, tell the user to start
  Docker Desktop and stop — don't retry. The local Supabase stack can't run
  without it.
- **Check `status` first** when the user's intent depends on what's already up.
- `start --watch` from chat runs servers in the background (the script nohups
  them); report the URLs (`:8000`, `:5174`) and that logs are in `.run-logs/`.
- **Don't run `./myrunstreak.sh tail`** in a tool call — it follows forever and
  blocks. Use `logs` for a snapshot.

## Safety
- **`db reset` wipes the local DB** (then re-applies all migrations). It only
  ever targets local Supabase, but still **confirm** before running it.
- **Never run `db reset` / `db down` while env is `prod`.** Check
  `./switch-env.sh status` first; if active env is `prod`, stop and confirm the
  user really wants to switch to local before any destructive db op.
- Switching to **prod** points the app at the live database — confirm before
  `./switch-env.sh prod`, and warn that subsequent actions hit production.
- If a command fails with a Docker error, the local stack needs Docker Desktop
  running — surface that, don't retry blindly.
