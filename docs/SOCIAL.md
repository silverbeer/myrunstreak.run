# Social & Community — Design (placeholder)

**Status:** Placeholder / future (2026-06-01)
**Owner:** @silverbeer
**Related:** `docs/GOALS_TRACKING.md`, `docs/GEAR_TRACKING.md`,
`docs/SOURCES_AND_IMPORT.md`

A social layer on top of the running data: **follow other runners**, **running
groups**, and **friendly competitions**. These build directly on what already
exists — the metric/goal engine, streaks, and community-aggregate plumbing — and
they fit the **invite-only** model unusually well: a trusted, small network makes
social features meaningful and keeps abuse surface low.

## Building blocks

### 1. Follow graph
- `follows` table: `(follower_id, followee_id, created_at)`, unique pair.
- A user's feed = recent runs/streak events from people they follow.
- **Visibility is the core design call.** Each user sets per-surface visibility
  (e.g. `public` | `followers` | `private`) for runs, streak, gear, stats.
  Following grants access only up to the followee's setting. Personal metric
  tables stay strict-RLS; the social feed reads through an explicit,
  consent-checked visibility layer — never a blanket cross-user read.

### 2. Running groups
Native to myrunstreak (**not** Strava-club-backed — Strava deprecated its Club
Activities/Members/Admins endpoints, effective Sept 1 2026).
- `groups` table + `group_members` (role: `owner` | `admin` | `member`).
- Group feed, group leaderboards, aggregate group stats (total miles, active
  streaks, etc.).
- **Join model:** invite or request-to-join; owners/admins moderate. No one is
  added to a group without consent.

### 3. Friendly competitions
The fun payoff — and mostly a **specialization of the goal engine**, not new
machinery.
- A competition = a **shared goal over a cohort over a window** + a
  **leaderboard** ranking participants by a metric.
- Reuses the goal taxonomy (`docs/GOALS_TRACKING.md`):
  - **Volume** — most miles this month; most push-ups.
  - **Frequency** — most run-days; longest streak.
  - **Head-to-head** — two runners, same window.
- `competitions` table (metric, kind, window, scope = group | followers | invite
  list) + `competition_participants` + a computed `leaderboard`.
- Motivation mechanics already specced (pace line, projection, badges, "don't
  break the chain") extend straight into the competitive context — e.g. "you're
  2 mi behind 2nd place with 4 days left."
- **Keep it friendly:** opt-in to join, leave anytime, no public shaming;
  celebrate effort (streaks kept, PRs) alongside raw rank.

## Privacy & safety (non-negotiable)

Social = exposing personal data to others, so:
- **Consent everywhere** — follow requests (for non-public users), group
  invites, competition joins are all opt-in.
- **Visibility model** gates every cross-user read; default conservative.
- **Block / report / leave** primitives from day one, even at small scale.
- Cross-user aggregates (group/competition stats) follow the same anonymization
  rules as `docs/GEAR_TRACKING.md` where they expose anyone but the viewer.

## Ties to the platform

- **Goals engine** powers competitions (shared goals + leaderboards) — biggest
  reuse.
- **Streaks/heatmaps** become social objects (compare chains, group streaks).
- **Community-aggregate** infra (scheduled job → materialized table) serves
  group/competition leaderboards without live cross-user fan-out.
- **Invite-only onboarding** (SB-96) is the natural substrate — the social graph
  starts as the invite graph.

## Open questions

- Visibility granularity: one global setting vs per-surface (runs/gear/stats)?
- Is the follow graph mutual (friends) or directional (followers), or both?
- Competition cadence: ad-hoc user-created vs platform-run monthly challenges?
- Leaderboard fairness across users with very different mileage — handicaps,
  divisions, or pure raw stats?
