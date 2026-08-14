# Data Sources, BYOK & Import — Design

**Status:** Partly shipped — single-run file import live (SB-99, 2026-08-14);
provider abstraction and bulk zip import still proposed (2026-06-01)
**Owner:** @silverbeer
**Related:** `docs/GOALS_TRACKING.md`, `docs/SMASHRUN_OAUTH.md`

## Goal

Ingest runs from multiple sources, connect each user's source account
(per-user credentials, see below), and **import runs from files** (single
activity or a bulk zip) for sources without a live API — or for backfill.

Today: SmashRun only (OAuth). The schema is already multi-source ready; this
formalizes the abstraction and adds file import.

> **Note on "BYOK".** The project name and earlier drafts say "bring your own
> key," but for our main sources that's a misnomer — **SmashRun and Strava are
> OAuth, the user never brings a key** (see [Credential models](#credential-models)).
> True paste-a-key BYOK applies only to services that issue per-user API keys.

## Positioning — SmashRun is the preferred source

**SmashRun is the recommended, first-class data source for myrunstreak.run**, and
**SmashRun paid (Pro) users are the primary target for the initial invite-only
cohort.** Rationale:

- SmashRun's API terms are permissive and free to integrate (no tiers, no stated
  user cap) — the opposite of Strava's 2026 gatekeeping.
- The owner already runs on SmashRun and wants to promote/support it.
- Targeting engaged SmashRun (Pro) runners means inviting users who already have
  rich run history to sync on day one.

Other sources (Strava, file import) are **secondary / resilience** paths, not the
front door. Onboarding copy and the "Connect a source" UI should lead with
SmashRun.

> Open: confirm whether SmashRun **free** accounts work over the API or whether
> Pro is required (see [Open questions](#open-questions)). Primary target is Pro
> users regardless, but the answer decides whether free users are even eligible.

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
  connect(user) -> stores credentials in user_sources   # OAuth flow (or paste-key, rare)
  fetch_activities(user_source, since) -> list[Activity]
  fetch_goals(user_source) -> Goal | None                # SmashRun only, optional
  normalize(raw) -> Activity                             # source format -> canonical
```

- **Registry** keyed by `source_type` → provider. The sync job and connect
  routes dispatch through it; no per-source `if` chains.
- `Activity` (canonical model) + `runs` upsert + dedup on
  `source_activity_id` / `external_id` stay the single normalization target for
  every provider, including import.

## Credential models

Two shapes, both stored per-user in `user_sources`. **Our primary sources use
the first one — there is no user-supplied key for SmashRun or Strava.**

1. **OAuth providers — SmashRun, Strava (and most others).**
   - The **app** holds **one** registered app credential (SmashRun app
     ID/secret; Strava client ID/secret), server-side, from the app secret /
     env. One registration covers *all* users — never per-user.
   - The **user** authorizes on the *provider's* site and we receive a per-user
     **OAuth token** (`access_token` / `refresh_token`). The user never sees,
     holds, or pastes a key.
   - This is **required**, not optional: SmashRun's terms forbid requesting or
     storing user credentials and mandate the OAuth flow; its app secret "may
     not be shared or used for more than one application." So per-user app
     secrets or credential prompts would **violate** the terms. See
     `docs/SMASHRUN_OAUTH.md`.
2. **Per-user API-key providers (the actual "BYOK" case).** Only for services
   that issue a key *to each user*. The user pastes their key; we store it.
   **Does not apply to SmashRun or Strava.** Reuse the token columns or add
   `api_key`.

**Security (must-fix before onboarding others):** the token columns in
`user_sources` are currently **plaintext**. Encrypt at rest (pgcrypto or
app-level envelope encryption) under strict RLS — never anon-readable. A leaked
OAuth token (or a pasted key) is a real breach. Tie this to the invite-only work
(SB-96) so no second user's tokens are ever stored in plaintext.

## Import — single run & bulk zip

A first-class ingestion path for sources without a live API, for backfill, and
as a manual fallback. Modeled as an **import provider** (add `import` to the
`source_type` enum, or reuse `other` with a marker).

### Single-run import — **shipped (SB-99)**

`POST /import/activity` (multipart: `file`, optional `timezone`). Upload one
activity file → parse → `Activity` → upsert into `runs`. Synchronous: a single
file parses in milliseconds, so it answers in the request.

- **Parsers** live in `src/shared/importers/` — one module per format, all
  producing the same `Activity` the SmashRun sync produces, so imported runs
  are stored, deduped and displayed exactly like synced ones.
- **Source row.** Imported runs hang off a `user_sources` row of type
  `import`, created lazily on a user's first upload
  (`UsersRepository.get_or_create_source`). Provenance is then a type, not a
  naming convention: a run came from a file iff its source is `import`.
- **Dedup key** (`source_activity_id`, prefixed by format):
  - TCX → `tcx-<Activity/Id>`; the id is stable across re-exports of the run.
  - SmashRun JSON → `smashrun-<activityId>`. Prefixed so an imported run can
    never collide with the same activity arriving later over OAuth sync.
  - GPX → `gpx-<sha256(file)[:24]>`; GPX states no id, so the bytes are the key.
- **GPS track.** GPX/TCX trackpoints are simplified and stored in `run_tracks`
  (`simplify_and_encode` → `upsert_track`), so an imported run gets a route map.
- **Timezone.** GPX and TCX record UTC. The request's `timezone` (default
  `America/New_York`) is what their timestamps are read into, and it is stored
  on the run — without it a 9pm run lands on tomorrow and breaks the streak.
  SmashRun JSON already states local time with an offset and is left alone.
- **Distance/duration.** TCX's stated lap totals win over the track. GPX has
  neither, so distance is summed over the trackpoints and duration excludes
  gaps longer than 60s (a paused watch, not a slow kilometre).
- **CLI:** `stk import <file> [--timezone ZONE]`, ahead of the upload UI (SB-418).

Re-uploading an already-imported file returns `status: "duplicate"` and writes
nothing — a re-upload is a reasonable thing to do, not an error.

### Bulk zip import
Upload a `.zip` (a full SmashRun/Strava data export, or many activity files) →
unzip → iterate → batch upsert with per-file results (imported / skipped-dup /
failed). This is the migration/backfill path; safe to re-run.

### Formats (phase the parsers)
- **Phase A (shipped, SB-99):** GPX + TCX (XML, simplest) and SmashRun export JSON.
- **Phase B (SB-421):** FIT (binary — needs `fitparse` / Garmin FIT SDK), Strava export.

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

Single-file import enforces this today: extension checked before any parsing
(415), 10 MB cap applied while streaming the upload so an oversized file costs
one 64 KB chunk rather than its full size (413), and XML parsed through
`defusedxml` — `xml.etree` is entity-bomb prone, and a size cap does not help
when a few hundred bytes of nested entities can exhaust memory.

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

- **SmashRun free vs Pro for API access.** The API Terms state no user-
  subscription requirement, but are silent on product-level gating; SmashRun
  does sell a paid "Pro" tier. Confirm whether **free** SmashRun accounts can be
  read over the API, or whether some/all data needs Pro. **Verify by (1) testing
  a free account against a dev build, and (2) emailing `api@smashrun.com`.**
  (Primary target is Pro users either way.)
- Encryption approach for stored tokens / keys: pgcrypto vs. app-level envelope.
- **Answered (SB-99):** `import` is its own `source_type` enum value
  (migration `20260814000000_add_import_source_type.sql`), not `other` + a flag.
- **Answered (SB-99):** uploaded files are parse-and-discard. Nothing is
  retained, so there is no new privacy surface; re-processing means
  re-uploading. Revisit only if bulk zip import (SB-419) needs resumability.
- **Open:** a run imported from a file and later synced from SmashRun lands as
  two rows — different `source_id`, so the upsert key can't see the collision.
  Cross-source dedup (same start time + distance) is not built.
