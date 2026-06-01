# Gear & Device Tracking + Community Aggregates — Design (placeholder)

**Status:** Placeholder / future (2026-06-01)
**Owner:** @silverbeer
**Related:** `docs/GOALS_TRACKING.md`, `docs/DATA_MODEL.md`,
`docs/SOURCES_AND_IMPORT.md`

Two fun, related features that share one shape:

> **per-run attribute → per-user accumulation → opt-in cross-user aggregate**

1. **Shoe / sneaker mileage** — which shoe was worn on a run, lifetime mileage
   per shoe, retire-at thresholds, brand comparisons.
2. **GPS device / watch** — which device recorded a run, exposed per run and
   rolled up.

Both become more interesting in aggregate: *"most popular shoe among myrunstreak
runners,"* *"average miles before retirement by brand,"* *"which watch is most
common."* That community layer is the differentiator — and the privacy-sensitive
part (see below).

## 1. Shoe / sneaker mileage

Strava and Garmin have "Gear"; **SmashRun does not** — so for SmashRun users this
is net-new value myrunstreak adds.

- **`gear` table** (per user): `brand`, `model`, `nickname`, `purchased_on`,
  `retire_at_km` (optional target), `is_active`, `image`/color.
- **Run → gear attribution**: `runs.gear_id` (nullable FK) or a join. A run has
  at most one pair of shoes.
- **Mileage** = `SUM(runs.distance_km)` per `gear_id`. Retirement nudge when a
  shoe nears `retire_at_km` (≈300–500 mi is the usual range — make it a
  per-shoe target, default suggested).
- **Sourcing**:
  - **Strava** exposes gear via the API (`activity.gear_id`, athlete shoes) →
    auto-import and map to `gear` rows.
  - **SmashRun / manual / import** → user assigns a shoe (default to "last used"
    for one-tap, matching the logging-friction principle in GOALS_TRACKING).

## 2. GPS device / watch

Partly already modeled: `runs` has a `device_type` enum
(`apple`|`google`|`garmin`|`other`) and `app_version`. This feature **extends
granularity and surfaces it**:

- Capture a finer **device/watch model** string where the source provides it
  (SmashRun/Strava activity device metadata), beyond the coarse enum.
- **Expose per run** in the UI, and roll up: "your runs by device," most-used
  watch, etc.
- No new attribution UI needed for synced runs — it rides along with the
  activity. Manual/import runs can optionally pick a device.

## 3. Community aggregates (the powerful, sensitive part)

Cross-user stats — popular brands, mileage-to-retirement curves, device share —
are the headline. They are also **personal data in aggregate**, so the design is
**privacy-first and non-negotiable**:

- **Opt-in only.** A user explicitly consents to contribute anonymized gear/
  device data to community stats. Default off. Ties to the privacy posture in
  `docs/GOALS_TRACKING.md` (personal tables stay strict-RLS).
- **Anonymized + k-anonymity.** Aggregates expose **counts/averages over cohorts
  only** — never a row traceable to a user. Suppress any bucket below a minimum
  cohort size (e.g. hide a stat unless ≥ N contributing users/runs).
- **Computed, not queried live.** A scheduled job materializes aggregates into a
  `community_aggregates` table/view (same CronJob pattern as `publish_status`);
  the API serves those, never raw cross-user reads. No endpoint can fan out over
  other users' rows.
- **Brand normalization.** Free-text brand/model needs canonicalization
  ("Nike Pegasus 40" vs "pegasus40") for meaningful comparison — a lookup /
  fuzzy-map step before aggregation.

## Ties to the platform

- Shoe mileage is a natural **metric** in the goals engine (a `gear_distance`
  metric type, volume goals like "500 mi on these shoes before retiring").
- Aggregation reuses the scheduled-job + Redis-cache infrastructure.
- The `gear` provider-import (Strava) slots into the `SourceProvider` abstraction
  (SB-98).

## Open questions

- Shoe attribution default: auto-assign "current active shoe" vs always prompt?
- Device model: store raw string + a normalized model, or just raw?
- Aggregate cohort minimum (k) and exactly which stats are safe to publish.
- Should community stats be a member perk (logged-in only) or partly public?
