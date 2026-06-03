# Goals & Multi-Metric Tracking — Design

**Status:** Proposed (2026-06-01)
**Owner:** @silverbeer

## Motivation

Today the app tracks one thing — running distance — and one cadence — the daily
streak. "Goals" are **read-only**: they mirror the yearly/monthly distance goals
a user sets on SmashRun.com (`goals` table, `backend/goals.py`, dashboard card).

We want to track and motivate across many domains:

- **Running** distance (already synced from SmashRun)
- **Body weight** — both the value (trend) and the *frequency* of weigh-ins
- **Push-ups** — daily counts with a target number
- **Weight training** — sessions, and later volume (sets × reps × load)

…and whatever comes next (planks, sleep, miles walked) **without rebuilding the
stack each time.**

## Core decision: a generic tracking engine

We do **not** add a `weights` table, a `pushups` table, a `lifting` table. That
is N features with N schemas, N endpoints, and N UIs forever. Instead, running
becomes "metric #1" in a generic engine of three primitives.

```
metric_types ──< metric_entries
metric_types ──< metric_goals
```

### `metric_types`

Defines *what* can be tracked. Adding a new trackable activity is one row.

| column            | meaning                                                        |
|-------------------|---------------------------------------------------------------|
| `key`             | stable slug: `running_distance`, `body_weight`, `pushups`, `lift_session` |
| `display_name`    | "Running distance", "Body weight", "Push-ups"                 |
| `unit`            | canonical unit: `km`, `kg`, `reps`, `session`                 |
| `aggregation`     | how entries roll up over a window: `sum` \| `count` \| `latest` \| `max` |
| `higher_is_better`| true for pushups/distance; false for body weight (a *loss* goal) |

Aggregation rule is the key abstraction:
- `sum` → push-ups, running distance ("how much total this month")
- `count` → weigh-ins, lift sessions ("how many times this week")
- `latest` → body-weight value ("what do I weigh now")
- `max` → PRs ("heaviest squat")

### `metric_entries`

The unified event log. **Everything is an entry** — a synced run, a logged set
of push-ups, a weigh-in. One table, one query surface.

| column        | meaning                                                       |
|---------------|---------------------------------------------------------------|
| `user_id`     | FK → `users.user_id`                                           |
| `metric_key`  | FK → `metric_types.key`                                        |
| `occurred_on` | DATE — the day this counts toward (local). Drives streaks/windows |
| `occurred_at` | TIMESTAMPTZ — precise time, nullable                          |
| `value`       | NUMERIC — miles, kg, reps, or `1` for a session/check-in      |
| `note`        | TEXT, optional                                                |
| `source`      | `manual` \| `smashrun` \| …                                   |
| `metadata`    | JSONB — exercise breakdown for a lift, etc.                   |
| `external_id` | dedup key for synced sources, nullable                        |

Running entries can be **projected from the existing `runs` table** (a view or a
sync-time insert) so we don't duplicate the SmashRun pipeline. `runs` already
carries `body_weight_kg` per run — those become `body_weight` entries for free.

### `metric_goals`

Native, **app-set** goals (not the SmashRun mirror). This is the new capability.

| column        | meaning                                                       |
|---------------|---------------------------------------------------------------|
| `user_id`     | FK → `users.user_id`                                           |
| `metric_key`  | FK → `metric_types.key`                                        |
| `kind`        | `volume` \| `frequency` \| `streak`  (see taxonomy below)     |
| `period`      | `year` \| `month` \| `week` \| `custom`                       |
| `period_start`/`period_end` | for `custom`; derived otherwise                |
| `target`      | NUMERIC — 1000 (mi), 3 (weigh-ins/wk), 1000 (pushups/mo)      |
| `comparator`  | `gte` (hit target) \| `lte` (stay under — weight)             |
| `rest_budget` | allowed misses per window before a streak/frequency goal "breaks" |
| `status`      | `active` \| `achieved` \| `archived`                          |

Progress is **always computed** from `metric_entries` over the goal's window per
the metric's aggregation rule — never stored stale.

## The taxonomy that drives motivation

Goals come in three shapes. Naming them is the design unlock — the user's own
words ("number of times I weigh in" vs. "number of push-ups") map straight onto
two of them.

1. **Volume** — accumulate toward a target. "1000 mi / year", "1000 push-ups /
   month". Progress = `sum(entries)` ÷ target. Motivated by a **pace line**.
2. **Frequency** — do the thing *N times* in a window. "Weigh in 3×/week", "lift
   4×/week". Progress = `count(distinct days with entry)` ÷ target. This is the
   **streak, generalized** to non-daily cadences.
3. **Streak** — the daily chain (run every day). A special case of frequency
   with target = every day and a `rest_budget`.

The current app only understands #3, only for running. The engine understands
all three for every metric.

## Qualified & layered streaks (Phase 1)

The base taxonomy counts *days with any entry*. Real streaks are richer — they
have a **per-period threshold** and they **nest**. Motivating example (a real
11-year streak):

- **Outer:** run **≥ 1 mile every day** — for 11+ years.
- **Inner:** within that, run **≥ 100 miles every month** — every month.
- **This month:** run **≥ 5 miles, at least 5 times**.

These need two additive concepts on `metric_goals` — **no change to
`metric_entries`, no data migration** (the run log already holds every value +
date; only goal *interpretation* changes):

### 1. Qualifier — "a unit only counts if it clears a threshold"

Add to a goal:
- `qualifier_unit` — `day | week | month`: the granularity each tally is measured over.
- `qualifier_threshold` + `qualifier_comparator` (`gte`/`lte`): the metric's
  aggregate over that unit must satisfy this to count.

A null qualifier = today's behavior ("any entry counts"). One field set powers
every example:

| Goal | kind | qualifier_unit | qualifier | target |
|---|---|---|---|---|
| Daily 1-mile streak | streak | day | sum ≥ 1 mi | (ongoing) |
| 100-mi-every-month streak | streak | **month** | sum ≥ 100 mi | (ongoing) |
| 5 mi × 5 times this month | frequency | day | sum ≥ 5 mi | 5 |
| plain "run every day" | streak | day | (none) | (ongoing) |

This also generalizes **streaks to period granularity**: a streak becomes
"consecutive **units** (day/week/month), each clearing the qualifier," counted
with `rest_budget` tolerance — not just consecutive days.

### 2. Nesting — "a streak within a streak"

The relationship ("the monthly-100 streak lives inside the daily streak") is
**presentation**, not math: the daily and monthly streaks are *independent*
qualified streaks computed over the same entries. Add an optional
`parent_goal_id` (self-FK on `metric_goals`) to express the nesting for grouped
display. The progress engine computes each layer independently; the parent link
only drives how they render (a streak nested inside a streak).

**Why it's additive:** a few nullable columns on `metric_goals` + extra branches
in `backend/metrics_progress.py` (per-unit aggregation + qualify check). The
entries model and existing goals are untouched — the generic-engine bet paying
off again. (Showing a multi-year streak needs the historical runs as entries;
SmashRun sync carries that history, with file import as the backfill path.)

## Motivation mechanics

Proven patterns, prioritized by impact:

- **Pace line (not raw %).** "1000 mi needs 2.7 mi/day — you're +12 mi ahead."
  Converts an abstract annual number into "did I do enough *today*." Highest-ROI
  single feature.
- **Projection.** "On pace for 1,043 mi 🎉" reads better than "47% complete."
  Show when a goal goes mathematically out of reach and suggest a revised target.
- **Generalized streaks + heatmap.** Reuse `StreakHeatmap.vue` for *every*
  metric — weigh-ins, push-ups, lifts each get a chain and a calendar.
- **Rest-day budget / streak-freeze** (Duolingo). You shouldn't lift 7×/week, so
  a missed day must not read as "broken." `rest_budget` absorbs N misses/window.
- **Milestones & badges.** First 1000-push-up month, 500 mi mark, 30-day chain.
- **Today card = the home surface.** Each active goal as a ring/bar showing
  today's contribution + pace status + a **one-tap quick-add**. Logging friction
  is what kills habit apps: logging must be one tap from the dashboard, never a
  form → nav → submit.

## UX principles

- **One-tap logging.** Push-ups = +/- stepper defaulting to last value. Weigh-in
  = type a number, done. Lift = "logged" check-in (volume detail optional).
- **Today card** ties long-horizon goals to a daily action. One glance: what
  advanced today, what needs attention, am I on pace.
- **Pace, not just percent**, everywhere a goal is shown.
- **Forgiveness** via rest budget so non-daily goals never show as failed.

## Relationship to the existing SmashRun goal mirror

**SmashRun stays the source of truth for running goals — permanently, not just
for now.** The owner defines running goals on SmashRun.com and they sync over;
this app does not replace SmashRun. So:

- **Running goals** = imported (`source = smashrun`) via the existing mirror
  (`goals` table, `backend/goals.py`, dashboard card #77/#78). Untouched.
- **Native goals** (`metric_goals`) cover everything SmashRun doesn't:
  body weight, push-ups, weight training, future metrics.
- The mirror is presented inside the unified engine as a read-only imported
  goal so the Today card shows running alongside the rest — but the app never
  writes running goals back. No big-bang migration; both coexist by design.

## Multi-tenant, invite-only & privacy

The platform must scale cleanly from 1 user to N, added **invite-only**.

- **Already multi-tenant.** `users` + `user_sources` + per-row `user_id` + RLS
  are in place; nothing here is single-user.
- **Invite-only onboarding.** Public signup disabled. An admin issues an invite
  (single-use token / link, optionally email-bound); the invitee completes
  Supabase Auth signup against that token, which provisions their `users` row.
  Track invites in an `invites` table (token, created_by, email, expires_at,
  redeemed_at, redeemed_by).
- **Privacy is a hard requirement for personal metrics.** Body weight and the
  like are sensitive. New tracking tables use **strict** RLS —
  `USING (user_id = auth.uid())`, **no anon escape**. The existing
  `OR auth.uid() IS NULL` escape exists only to serve the *public* running
  streak (the qualityplaybook.dev embed / `status.json`); it must NOT be copied
  onto `metric_entries` / `metric_goals`. Public surface = running streak only;
  weight/strength data is never anon-readable.

## Installable PWA (like the MT app)

The frontend (Vue 3 + Vite) ships as an **installable PWA** — add-to-home-screen
on phone, no app-store. Use `vite-plugin-pwa` (manifest + service worker).

- **Offline-first logging.** Logging is the critical path and often happens at
  the gym with bad signal. Queue `metric_entries` locally (IndexedDB) and sync
  when back online. The unified entry log makes this clean: one offline queue,
  one replay path, for every metric.
- Installable + offline + one-tap logging is the whole UX bet — it must feel
  like a native habit tracker, not a website.

## DRY: shared platform packages (cross-repo)

Recurring pattern across silverbeer repos (myrunstreak, missing-table,
match-scraper, qualityplaybook): each is a Python backend + a web frontend that
re-implement the same plumbing. Goal: extract shared packages so new apps start
from a common base.

- **Backend (Python, UV):** a `silverbeer-core` package (UV git dep / workspace)
  for Supabase client + auth, repository base class, config/secrets, common
  Pydantic models, units conversion.
- **Frontend (TS/Vue):** a shared component + composable library — `StatCard`,
  `StreakHeatmap`, the auth store, the API client, a Tailwind preset / design
  tokens.
- **Approach: extract-as-you-go (rule of three).** Don't pre-build a framework.
  Build the metric engine here with clean boundaries, then lift the reusable
  pieces into shared packages once the 2nd repo needs them. Tracked as a
  cross-repo initiative, not a blocker on this project.

## Schema conventions (match existing migrations)

- UUID PKs via `gen_random_uuid()`.
- FKs `ON DELETE CASCADE` to `users(user_id)`.
- RLS enabled. **Public-streak tables** may keep the
  `USING (user_id = auth.uid() OR auth.uid() IS NULL)` anon escape; **personal
  metric tables** (`metric_entries`, `metric_goals`, `invites`) use strict
  `USING (user_id = auth.uid())` — no anon.
- `updated_at` via the existing `update_updated_at_column()` trigger.
- Distances stored canonical (km); convert to miles at the presentation edge
  (`km_to_miles` in `backend/goals.py`).

## Phasing

- **Phase 0 — foundation + first tracking (this week).**
  Fix `README.md` + `DATA_MODEL.md`. Add `metric_types` / `metric_entries` /
  `metric_goals` migrations (strict RLS). Seed `body_weight` + `pushups`.
  One-tap logging + a Today card. Goal: owner is tracking new metrics on June 1.
- **Phase 1 — pace, consistency & install.** Pace/projection engine.
  Generalized streak + heatmap per metric. Frequency goals (weigh-in count).
  **Qualified & layered streaks** (per-period threshold + nesting — see section
  above). **Installable PWA + offline logging queue.**
- **Phase 2 — strength + rewards.** Weight training (session check-ins, then
  volume). Milestones/badges. Rest-day budget / streak-freeze.
- **Phase 3 — polish + nudges.** UX pass; push nudges via the existing
  `cronjob-publish-status` path ("2 mi behind — easy catch-up this week").

Cross-cutting, sequenced by need rather than phase:

- **Invite-only onboarding** — required *before inviting user #2*. `invites`
  table + admin invite issuance + gated signup. Do this when the 2nd user is
  imminent; the data model is already multi-tenant so it does not block Phase 0
  for the owner.
- **Shared platform packages (DRY)** — cross-repo initiative, extract-as-you-go.
  Not a blocker; build with clean boundaries and lift later.

## Open questions

- Units: app shows miles; store km canonically. Body weight — lb or kg display?
- Volume goal for lifting: session count (simple) vs. tonnage (sets×reps×load)?
- Invites: email-bound single-use, or shareable link with expiry?

## Resolved

- **SmashRun stays source of truth for running goals** — synced, never replaced.
  Native engine covers only non-running metrics.
