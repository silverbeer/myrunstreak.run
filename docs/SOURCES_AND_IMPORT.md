# Data Sources, BYOK & Import — Design

**Status:** Proposed (2026-06-01)
**Owner:** @silverbeer
**Related:** `docs/GOALS_TRACKING.md`, `docs/SMASHRUN_OAUTH.md`

## Goal

Ingest runs from multiple sources, let users **bring their own credentials
(BYOK)**, and **import runs from files** (single activity or a bulk zip) for
sources without a live API — or for backfill/migration.

Today: SmashRun only (OAuth). The schema is already multi-source ready; this
formalizes the abstraction and adds file import.

## What already exists

- `user_sources` table: `source_type` enum (`smashrun` | `strava` | `garmin` |
  `other`), one row per (user, source). Holds per-user OAuth tokens
  (`access_token` / `refresh_token` / `token_expires_at`), `source_user_id`,
  `source_username`, `is_active`, `last_sync_at`.
- SmashRun OAuth connect flow (`docs/SMASHRUN_OAUTH.md`), sync job
  (`backend/jobs/sync_runs.py`), `runs` table normalized via the `Activity`
  Pydantic model.

So multi-source/BYOK is a **formalization**, not a rebuild.

## Provider abstraction

One interface per source. SmashRun is provider #1; new sources implement the
same contract and register by `source_type`.

```
SourceProvider:
  connect(user) -> stores credentials in user_sources   # OAuth dance OR BYOK key
  fetch_activities(user_source, since) -> list[Activity]
  fetch_goals(user_source) -> Goal | None                # SmashRun only, optional
  normalize(raw) -> Activity                             # source format -> canonical
```

- **Registry** keyed by `source_type` → provider. The sync job and connect
  routes dispatch through it; no per-source `if` chains.
- `Activity` (canonical model) + `runs` upsert + dedup on
  `source_activity_id` / `external_id` stay the single normalization target for
  every provider, including import.

## BYOK — bring your own credentials

Two credential shapes, both stored per-user in `user_sources`:

1. **OAuth providers** (SmashRun today; Strava/Garmin later) — the user
   authorizes; we store their tokens. The *app* still holds the OAuth client
   creds (read from env, per fix #74) — that's app config, not the user's key.
2. **API-key providers** — the user pastes their own key/token (true BYOK).
   Stored in `user_sources` (reuse the token columns, or add `api_key`).

**Security (must-fix for BYOK):** credentials in `user_sources` are currently
**plaintext columns**. Before onboarding other users' keys, encrypt at rest
(pgcrypto or app-level envelope encryption) and keep these columns under strict
RLS — never anon-readable. A leaked third-party running key is a real breach.

## Import — single run & bulk zip

A first-class ingestion path for sources without a live API, for backfill, and
as a manual fallback. Modeled as an **import provider** (add `import` to the
`source_type` enum, or reuse `other` with a marker).

### Single-run import
Upload one activity file → parse → `Activity` → upsert into `runs`. Idempotent
via dedup key (`source_activity_id` or a content hash) so re-uploads don't
duplicate.

### Bulk zip import
Upload a `.zip` (a full SmashRun/Strava data export, or many activity files) →
unzip → iterate → batch upsert with per-file results (imported / skipped-dup /
failed). This is the migration/backfill path; safe to re-run.

### Formats (phase the parsers)
- **Phase A:** GPX + TCX (XML, simplest) and SmashRun export JSON.
- **Phase B:** FIT (binary — needs `fitparse` / Garmin FIT SDK), Strava export.

### Processing model
- Small single file → synchronous parse + upsert in the request.
- Zip / large → **background job** (`backend/jobs/`, same pattern as
  `sync_runs.py`); upload returns a job id, UI polls progress. Large exports must
  not block a request.

### Upload safety
- Enforce max upload size and per-file size; **guard against zip bombs**
  (entry-count + uncompressed-size caps).
- File-type allowlist (`.gpx`/`.tcx`/`.fit`/`.json`/`.zip`); reject everything
  else. Scope all writes to the authenticated user.

## Strava specifics

Strava is a planned provider, but its Developer Program (2026 changes) constrains
how we integrate. Key points, from the June 2026 Strava API Team announcement:

- **Direct API only — no intermediary/MCP layer.** Strava now *bans* apps that
  route athlete data through third-party intermediary platforms (their anti-AI-
  scraping measure). Our `SourceProvider` for Strava must be a **direct OAuth
  integration**, which is explicitly still supported. We must **not** ingest
  Strava data through Strava's official MCP or any proxy — that is the banned
  pattern. (Strava's MCP is end-user AI tooling, not a data source for apps.)
- **Tier caps scaling.** *Standard Tier* allows **up to 10 athletes** (self-serve,
  higher rate limits, Strava subscription required for the developer). Past 10
  users we need **Extended Access Tier** (Strava review/approval, greater user
  capacity, no subscription). The invite-only 1→N plan must account for this cap —
  Strava gates growth differently than SmashRun.
- **Free athlete export feeds our import path.** Every Strava athlete can download
  their data for free at any time. That export is a first-class input to the
  single-run / bulk-zip importer below — a low-friction, policy-safe path that
  sidesteps tier/subscription limits.
- **June 1 2027 technical changes** to design for up front:
  - OAuth tokens must be sent in **request headers**, not form params.
  - Base URL changes: `https://www.strava.com/api/v3` → `https://www.api-v3.strava.com`.
  - Use the new `oauth/revoke` endpoint; `oauth/deauthorize` is retired.

> Inverse idea (separate, future): rather than consuming Strava's MCP, myrunstreak
> could **expose its own MCP** over unified data (SmashRun + Strava + manual
> metrics), so "ask AI about my training" works across all sources. Complementary
> to Strava's MCP, not dependent on it. Tracked as a placeholder issue.

## Ties to the rest of the platform

- Imported runs become `runs` rows → projected into `metric_entries`
  (`running_distance`, and `body_weight` where present) for the goals engine.
- New sources/import benefit the DRY effort: the provider interface +
  `Activity` normalizer are prime candidates to lift into `silverbeer-core`.

## Open questions

- Encryption approach for BYOK creds: pgcrypto vs. app-level envelope.
- `import` as a new `source_type` enum value vs. reuse `other` + a flag.
- Where do uploaded raw files live — ephemeral (parse-and-discard) vs. retained
  in object storage for re-processing? Retention has privacy implications.
