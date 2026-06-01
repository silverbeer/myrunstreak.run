# Data Sources, BYOK & Import — Design

**Status:** Proposed (2026-06-01)
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

- **SmashRun free vs Pro for API access.** The API Terms state no user-
  subscription requirement, but are silent on product-level gating; SmashRun
  does sell a paid "Pro" tier. Confirm whether **free** SmashRun accounts can be
  read over the API, or whether some/all data needs Pro. **Verify by (1) testing
  a free account against a dev build, and (2) emailing `api@smashrun.com`.**
  (Primary target is Pro users either way.)
- Encryption approach for stored tokens / keys: pgcrypto vs. app-level envelope.
- `import` as a new `source_type` enum value vs. reuse `other` + a flag.
- Where do uploaded raw files live — ephemeral (parse-and-discard) vs. retained
  in object storage for re-processing? Retention has privacy implications.
